"""CPU tests for the official remote byte layout and the read-only CLI."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import csv
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
from unitree_sdk2py.utils.crc import CRC

import a2_robot
import a2_dds
from remote_input import AXES, BUTTONS, RemoteDecoder, RemoteStatistics
from a2_policy import COMMANDS


def payload(*, lx=0., rx=0., ry=0., ly=0., buttons=0):
    frame = bytearray(40)
    frame[:2] = b"\xaa\x55"
    struct.pack_into("<H", frame, 2, buttons)
    for offset, value in zip((4, 8, 12, 20), (lx, rx, ry, ly)):
        struct.pack_into("<f", frame, offset, value)
    return bytes(frame)


class DecoderTests(unittest.TestCase):
    def test_one_axis_at_a_time(self):
        decoder = RemoteDecoder()
        stats = RemoteStatistics()
        center = decoder.decode(payload(lx=.01, ly=-.02), 0.)
        self.assertEqual(center.command, (0., 0., 0.))
        self.assertEqual(center.status, "centered_axes_link_unknown")
        stats.add(center)
        expected = {
            ("ly", 1): COMMANDS["forward"],
            ("ly", -1): COMMANDS["reverse"],
            ("lx", 1): (0., -.2, 0.),
            ("lx", -1): COMMANDS["lateral"],
            ("rx", 1): (0., 0., -.3),
            ("rx", -1): COMMANDS["yaw"],
            ("ry", 1): (0., 0., 0.),
            ("ry", -1): (0., 0., 0.),
        }
        for i, ((axis, sign), cmd) in enumerate(expected.items(), 1):
            with self.subTest(axis=axis, sign=sign):
                result = decoder.decode(payload(**{axis:sign}), float(i))
                self.assertEqual(result.axes, tuple(sign if key==axis else 0. for key in AXES))
                self.assertEqual(result.command, cmd)
                stats.add(result)
        axes = stats.summary()["axes"]
        for name in AXES:
            self.assertEqual(axes[name]["min"], -1.)
            self.assertEqual(axes[name]["max"], 1.)
            self.assertEqual(axes[name]["isolated_samples"], {"positive":1,"negative":1})
        self.assertAlmostEqual(axes["ly"]["center_median"], -.02, places=6)
        self.assertAlmostEqual(decoder.decode(payload(ly=.54), 10.).command[0], .15, places=6)

    def test_buttons_and_link_ambiguity(self):
        decoder = RemoteDecoder()
        for i, name in enumerate(BUTTONS):
            sample = decoder.decode(payload(buttons=1<<i), float(i))
            self.assertEqual(sample.buttons, (name,))
            self.assertEqual(sample.button_mask, 1<<i)
            self.assertEqual(sample.command, (0.,0.,0.))
        active = payload(ly=.8)
        decoder.decode(active, 20.)
        same = decoder.decode(active, 21.)
        self.assertAlmostEqual(same.unchanged_ms, 1000.)
        self.assertEqual(same.status, "active_axes_link_unknown")
        self.assertEqual(decoder.decode(bytes(40), 22.).status, "all_zero_payload_link_unknown")
        for frame in (payload(lx=float("nan")), payload(rx=3.), b"\x01"):
            sample = decoder.decode(frame, 23.)
            self.assertTrue(sample.status.startswith("invalid_"))
            self.assertEqual(sample.command, (0.,0.,0.))


class FixtureLowState:
    def __init__(self, packets, stop=False):
        self.packets = list(packets)
        self.stop = stop
        self.tick = 0
        self.crc = CRC()

    def wait(self, predicate, timeout):
        if self.stop and self.tick>=len(self.packets):
            raise TimeoutError("no new DDS tick")
        packet = self.packets[min(self.tick,len(self.packets)-1)]
        self.tick += 1
        msg = unitree_go_msg_dds__LowState_()
        msg.tick = self.tick
        msg.imu_state.quaternion = [1.,0.,0.,0.]
        msg.wireless_remote = list(packet)
        msg.crc = self.crc.Crc(msg)
        assert predicate(msg,0.)
        return msg,time.monotonic()


class ShadowCliTests(unittest.TestCase):
    def run_fixture(self, path, fixture, mode="shadow", extra=()):
        argv = ["a2_robot.py",mode,"--iface","eth10","--seconds",".6",
                "--policy-update","student","--csv",str(path),"--remote",*extra]
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys,"argv",argv))
            stack.enter_context(patch.object(a2_robot.socket,"if_nameindex",return_value=[(1,"eth10")]))
            channel = stack.enter_context(patch.object(a2_robot,"ChannelFactoryInitialize"))
            latest = stack.enter_context(patch.object(a2_robot,"Latest",return_value=fixture))
            forbidden = [
                stack.enter_context(patch.object(a2_robot,"MotorCommands",side_effect=AssertionError("LowCmd constructed"))),
                stack.enter_context(patch.object(a2_robot,"bounded_command_publisher",side_effect=AssertionError("LowCmd publisher"))),
                stack.enter_context(patch.object(a2_dds,"ChannelPublisher",side_effect=AssertionError("DDS publisher"))),
                stack.enter_context(patch.object(a2_dds,"ChannelFactory",side_effect=AssertionError("CreateChannel"))),
                stack.enter_context(patch("unitree_sdk2py.comm.motion_switcher.motion_switcher_client.MotionSwitcherClient",side_effect=AssertionError("mode change"))),
                stack.enter_context(patch("unitree_sdk2py.go2.sport.sport_client.SportClient",side_effect=AssertionError("Sport"))),
            ]
            if mode!="shadow" or extra:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    a2_robot.main()
                self.assertEqual(caught.exception.code,2)
                channel.assert_not_called()
                latest.assert_not_called()
            else:
                with redirect_stdout(io.StringIO()):
                    status = a2_robot.main()
                channel.assert_called_once_with(0,"eth10")
                latest.assert_called_once_with("rt/lowstate",a2_robot.LowState_)
            for mock in forbidden:
                mock.assert_not_called()
        if mode=="shadow" and not extra:
            return status

    def test_shadow_uses_only_subscriber_and_records_axes(self):
        packets = [payload(), payload(ly=1), payload(ly=-1), payload(lx=1),payload(lx=-1),
                   payload(rx=1),payload(rx=-1),payload(ry=1),payload(ry=-1),payload(buttons=1<<8),bytes(40),payload()]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"remote.csv"
            self.assertEqual(self.run_fixture(path,FixtureLowState(packets)),0)
            summary=json.loads(path.with_suffix(".summary.json").read_text())
            with path.open() as file:
                rows=list(csv.DictReader(file))
            self.assertEqual(summary["samples"],len(rows))
            self.assertGreaterEqual(len(rows),len(packets))
            self.assertEqual(summary["mode_changes_sent"],0)
            self.assertEqual(summary["sport_commands_sent"],0)
            self.assertEqual(summary["lowcmd_publishers_created"],0)
            self.assertFalse(summary["radio_link_verified"])
            self.assertEqual(rows[0]["cycle_period_ms"],"")
            self.assertTrue(all(float(r["cycle_period_ms"])>0 for r in rows[1:]))
            self.assertTrue(all(len(json.loads(r["target_rad_assuming_matching_frames"]))==12 for r in rows))
            self.assertTrue(any(r["buttons"]=='["A"]' for r in rows))
            self.assertTrue(any(r["remote_status"]=="all_zero_payload_link_unknown" for r in rows))
            print("Synthetic CLI axes, 12 targets, timestamps and zero control endpoints verified",file=sys.stderr)

    def test_timeout_retains_partial_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"timeout.csv"
            self.assertEqual(self.run_fixture(path,FixtureLowState([payload()],stop=True)),1)
            summary=json.loads(path.with_suffix(".summary.json").read_text())
            self.assertEqual(summary["status"],"failed")
            self.assertEqual(summary["reason"],"lowstate_timeout_or_tick_stalled")
            self.assertEqual(summary["samples"],1)
            self.assertEqual(summary["lowcmd_publishers_created"],0)

    def test_remote_is_shadow_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode, extra in (("bench",()),("observe",()),("shadow",("--commands-stdin",))):
                self.run_fixture(Path(tmp)/"unused.csv",FixtureLowState([payload()]),mode,extra)


if __name__ == "__main__":
    unittest.main()
