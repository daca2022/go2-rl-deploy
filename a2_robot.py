"""Read an Ethernet Go2 or run a short A2 low-level trial on a supported bench."""
import argparse
import csv
import json
from pathlib import Path
from types import SimpleNamespace
import signal
import socket
import time

import numpy as np
from unitree_sdk2py.core.channel import ChannelFactoryInitialize

from a2_dds import STATE_TOPIC, CRC, Latest, LowState_, MotorCommands, bounded_command_publisher, state_joints
from a2_policy import A2Policy, COMMANDS, JOINT_NAMES, KD, KP, PERIOD, POLICY_UPDATES, SDK_IDS, SIM_JOINT_RANGE, gravity_body, parse_policy_update

SEND_PERIOD = .002
MAX_STATE_AGE = .04
ZERO = np.zeros(12)


def vector(raw, name, shape):
    values = np.asarray(raw[name], dtype=float)
    if values.shape != shape or not np.isfinite(values).all():
        raise ValueError(f'{name} must have shape {shape} and finite entries')
    return values


def load_profile(path, iface):
    profile = json.loads(path.read_text())
    if profile['iface'] != iface or profile['joint_names'] != JOINT_NAMES:
        raise ValueError('Bench profile has a different interface or joint order')
    if not str(profile['robot_firmware']).strip() or profile['frames_verified'] is not True:
        raise ValueError('Record firmware and verify joint/IMU frames on the bench')
    signs = vector(profile, 'sign', (12,))
    offsets = vector(profile, 'sdk_zero_rad', (12,))
    limits = vector(profile, 'joint_limits_rad', (12,2))
    p = vector(profile, 'kp', (12,))
    d = vector(profile, 'kd', (12,))
    damping = vector(profile, 'stop_kd', (12,))
    nominal_error = vector(profile, 'max_start_error_rad', (12,))
    target_error = vector(profile, 'max_target_error_rad', (12,))
    torque = vector(profile, 'max_estimated_torque_nm', (12,))
    if (not np.isin(signs, (-1., 1.)).all()
            or np.any(limits[:,0] >= limits[:,1])
            or np.any(limits[:,0] < SIM_JOINT_RANGE[:,0])
            or np.any(limits[:,1] > SIM_JOINT_RANGE[:,1])
            or np.any((p <= 0) | (p > KP)) or np.any((d <= 0) | (d > KD))
            or np.any((damping <= 0) | (damping > KD))
            or np.any((nominal_error <= 0) | (nominal_error > .25))
            or np.any((target_error <= 0) | (target_error > .12))
            or np.any((torque <= 0) | (torque > 5.))):
        raise ValueError('Bench profile exceeds joint or commissioning envelopes')
    return signs, offsets, limits, p, d, damping, nominal_error, target_error, torque


def inspect_state(msg, encoder):
    if msg.crc != encoder.crc.Crc(msg):
        raise ValueError('Invalid LowState CRC')
    q, dq = state_joints(msg)
    quat = np.array(msg.imu_state.quaternion)
    gyro = np.array(msg.imu_state.gyroscope)
    if (not np.isfinite(np.concatenate((q,dq,quat,gyro))).all()
            or not .98 <= np.linalg.norm(quat) <= 1.02):
        raise ValueError('Invalid joint positions, velocity or IMU')
    return q, dq, quat, gyro


def stop_on_signal(_signum, _frame):
    raise KeyboardInterrupt


def capture(args, rx, encoder, actor):
    started = time.monotonic()
    last = None
    stream = None
    if args.commands_stdin:
        from teleop_input import StdinCommands, VELOCITIES

        stream = StdinCommands(0)
    with args.csv.open('x', newline='') as file:
        writer = csv.writer(file)
        header = ['pc_time_s', 'dds_tick', 'age_ms', 'imu_wxyz', 'gyro_rad_s',
                  'q_sdk_in_actor_order_rad', 'dq_sdk_in_actor_order_rad_s', 'tau_est_sdk_nm',
                  'target_rad_assuming_matching_frames']
        writer.writerow(header + (['request', 'cmd_vx', 'cmd_vy', 'cmd_yaw', 'policy_ms'] if stream else []))
        if stream:
            print("SHADOW_INPUT_READY", flush=True)
        while time.monotonic() - started < args.seconds:
            cycle_started = time.monotonic()
            msg, stamp = rx.wait(lambda m, _: m.tick != last, .1)
            if time.monotonic()-stamp > MAX_STATE_AGE:
                raise TimeoutError('Stale LowState')
            last = msg.tick
            q, dq, quat, gyro = inspect_state(msg, encoder)
            key = stream.sample(time.monotonic()) if stream else None
            request = VELOCITIES[key] if stream else COMMANDS[args.command]
            policy_started = time.monotonic()
            targets = actor.step(quat, gyro, q, dq, request) if actor else None
            policy_ms = (time.monotonic()-policy_started)*1000
            row = [time.monotonic()-started, last, (time.monotonic()-stamp)*1000,
                   quat.tolist(), gyro.tolist(), q.tolist(), dq.tolist(),
                   [msg.motor_state[i].tau_est for i in SDK_IDS],
                   targets.tolist() if targets is not None else '']
            writer.writerow(row + ([key, *request, policy_ms] if stream else []))
            file.flush()
            if stream and stream.closed:
                break
            time.sleep(max(0., PERIOD - (time.monotonic() - cycle_started)) if stream else PERIOD)
    print(json.dumps({'mode': args.mode, 'policy_update': args.policy_update if actor else None,
                      'lowcmd_publishers_created': 0, 'csv': str(args.csv)}))



def capture_remote(args, rx, actor):
    """Read LowState, calculate and log hypothetical targets; no command endpoints."""
    from remote_input import AXES, RemoteDecoder, RemoteStatistics

    encoder = SimpleNamespace(crc=CRC())
    decoder = RemoteDecoder()
    stats = RemoteStatistics()
    started = previous = last = None
    samples = 0
    periods, inference, ages = [], [], []
    status, reason = "complete", None
    summary_path = args.csv.with_suffix(".summary.json")
    if summary_path.exists():
        raise FileExistsError(summary_path)
    with args.csv.open("x", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["pc_time_s","dds_tick","age_ms","cycle_period_ms","policy_ms",
                         *AXES,"button_mask","buttons","remote_payload_hex","remote_status",
                         "unchanged_payload_ms","cmd_vx","cmd_vy","cmd_yaw","imu_wxyz",
                         "gyro_rad_s","q_sdk_in_actor_order_rad","dq_sdk_in_actor_order_rad_s",
                         "tau_est_sdk_nm","target_rad_assuming_matching_frames"])
        print("SHADOW_REMOTE_READY", flush=True)
        try:
            while started is None or time.monotonic()-started < args.seconds:
                try:
                    msg, stamp = rx.wait(lambda m, _: m.tick != last, 4. if started is None else .1)
                except TimeoutError:
                    status, reason = "failed", "lowstate_timeout_or_tick_stalled"
                    break
                selected = time.monotonic()
                age = selected-stamp
                if age > MAX_STATE_AGE or age < 0 or not np.isfinite(age):
                    status, reason = "failed", "lowstate_stale"
                    break
                if started is None:
                    started = selected
                if selected-started >= args.seconds:
                    break
                last = msg.tick
                q, dq, quat, gyro = inspect_state(msg, encoder)
                sample = decoder.decode(msg.wireless_remote, selected)
                policy_started = time.monotonic()
                target = actor.step(quat, gyro, q, dq, sample.command)
                policy_ms = (time.monotonic()-policy_started)*1000
                gap = None if previous is None else (selected-previous)*1000
                previous = selected
                ages.append(age*1000)
                inference.append(policy_ms)
                if gap is not None:
                    periods.append(gap)
                stats.add(sample)
                writer.writerow([selected-started,last,age*1000,gap,policy_ms,*sample.axes,
                                 sample.button_mask,json.dumps(sample.buttons),sample.payload_hex,
                                 sample.status,sample.unchanged_ms,*sample.command,quat.tolist(),gyro.tolist(),
                                 q.tolist(),dq.tolist(),[msg.motor_state[i].tau_est for i in SDK_IDS],
                                 target.tolist()])
                file.flush()
                samples += 1
                time.sleep(max(0., PERIOD-(time.monotonic()-selected)))
        except (ValueError, RuntimeError, TimeoutError) as exc:
            status, reason = "failed", str(exc)
        except KeyboardInterrupt:
            status, reason = "interrupted", "operator_interrupt"
    def timing(values):
        return {"median":float(np.median(values)), "p95":float(np.percentile(values,95)),
                "max":float(max(values))} if values else None
    result = {"mode":"shadow","input":"wireless_remote","policy_update":args.policy_update,
              "status":status,"reason":reason,"samples":samples,"requested_seconds":args.seconds,
              "lowcmd_publishers_created":0,"sport_commands_sent":0,"mode_changes_sent":0,
              "csv":str(args.csv),"summary":str(summary_path),
              "nominal_period_ms":PERIOD*1000,"actual_period_ms":timing(periods),
              "policy_ms":timing(inference),"lowstate_age_ms":timing(ages),**stats.summary()}
    with summary_path.open("x") as file:
        json.dump(result,file,indent=2)
        file.write("\n")
    print(json.dumps(result),flush=True)
    return 0 if status=="complete" and samples else 1


def bench(args, rx, encoder, actor, config):
    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

    signs, offsets, limits, p, d, damping, start_error, target_error, torque = config
    switch = MotionSwitcherClient()
    switch.SetTimeout(1.)
    switch.Init()
    code, mode = switch.CheckMode()
    if code != 0 or not isinstance(mode, dict) or mode.get('name') != '':
        raise RuntimeError('MotionSwitcher must report no active motion service')
    tx = bounded_command_publisher()
    msg, _ = rx.fresh(MAX_STATE_AGE)
    q, dq, quat, gyro = inspect_state(msg, encoder)
    initial = signs*(q-offsets)
    if (np.any(np.abs(initial-actor.q0) > start_error) or np.max(np.abs(dq)) > .3
            or gravity_body(quat)[2] > -.95):
        raise RuntimeError('Bench requires a stationary, upright initial pose close to training pose')
    if np.any(actor.q0 < limits[:,0]) or np.any(actor.q0 > limits[:,1]):
        raise ValueError('Physical joint envelope must contain nominal pose')

    actor.step(quat, gyro, initial, signs*dq, COMMANDS[args.command])
    actor.reset()
    started = time.monotonic()
    previous_send = started
    next_send, next_policy = started, started
    first_command = False
    last_state_tick = None
    last_new_state = started
    records = []
    with args.csv.open('x', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['t_s','state_tick','state_age_ms','loop_gap_ms','q_rad','dq_rad_s',
                         'raw_target_rad','sent_target_rad','tau_est_sdk_nm'])
        try:
            while (now := time.monotonic()) - started < args.seconds:
                if now < next_send:
                    time.sleep(next_send-now)
                    continue
                if now-next_send > .010:
                    raise TimeoutError('LowCmd loop missed its deadline')
                gap = now-previous_send
                previous_send = now
                next_send = max(next_send+SEND_PERIOD, now+SEND_PERIOD)
                msg, stamp = rx.fresh(MAX_STATE_AGE)
                if msg.tick != last_state_tick:
                    last_state_tick = msg.tick
                    last_new_state = now
                if now-last_new_state > MAX_STATE_AGE:
                    raise TimeoutError('LowState tick stopped changing')
                sdk_q, sdk_dq, quat, gyro = inspect_state(msg, encoder)
                q = signs*(sdk_q-offsets)
                dq = signs*sdk_dq
                measured_torque = np.array([msg.motor_state[i].tau_est for i in SDK_IDS])
                if (np.any(q < limits[:,0]) or np.any(q > limits[:,1]) or gravity_body(quat)[2] > -.9
                        or np.max(np.abs(dq)) > 2. or not np.isfinite(measured_torque).all()
                        or np.any(np.abs(measured_torque) > torque)):
                    raise RuntimeError('Bench state left the checked envelope')
                due = now >= next_policy
                if due:
                    if now-next_policy > .010:
                        raise TimeoutError('Policy loop missed its deadline')
                    raw_target = actor.step(quat, gyro, q, dq, COMMANDS[args.command])
                    next_policy += PERIOD
                # At the joint servo, torque is approximately kp*(q_target-q)-kd*dq.
                torque_lower = q + (d*dq-torque)/p
                torque_upper = q + (d*dq+torque)/p
                lower = np.maximum.reduce((limits[:,0], q-target_error, torque_lower))
                upper = np.minimum.reduce((limits[:,1], q+target_error, torque_upper))
                if np.any(lower > upper):
                    raise RuntimeError('No command satisfies bench position and torque bounds')
                target = np.clip(raw_target, lower, upper)
                send_time = time.monotonic()
                if send_time - started >= args.seconds:
                    break
                if send_time - stamp > MAX_STATE_AGE or send_time - now > .010:
                    raise TimeoutError('LowCmd became stale before publishing')
                first_command = True
                if not tx.Write(encoder.fill(offsets+signs*target, p, d)):
                    raise RuntimeError('LowCmd write failed')
                if due:
                    records.append([now-started, msg.tick, (send_time-stamp)*1000, gap*1000,
                                    q.tolist(),dq.tolist(),raw_target.tolist(),target.tolist(),
                                    measured_torque.tolist()])
        finally:
            if first_command:
                deadline = time.monotonic()+.2
                sent = 0
                while time.monotonic() < deadline:
                    if tx.Write(encoder.fill(ZERO, ZERO, damping)):
                        sent += 1
                    time.sleep(SEND_PERIOD)
                print(json.dumps({'damping_messages_sent':sent, 'physical_stop_requires_operator':True}), flush=True)
            writer.writerows(records)
    if not first_command:
        raise RuntimeError('Bench window ended without a command')
    print(json.dumps({'mode':'bench', 'policy_update':args.policy_update,
                      'policy_steps':actor.tick, 'csv':str(args.csv)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('observe','shadow','bench'))
    parser.add_argument('--iface', required=True)
    parser.add_argument('--csv', required=True, type=Path)
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('--command', choices=COMMANDS, default='forward')
    parser.add_argument('--policy-update', type=parse_policy_update, choices=POLICY_UPDATES, default=2000)
    parser.add_argument('--bench-profile', type=Path)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--commands-stdin', action='store_true', help='recibir teclas por stdin, solo en shadow')
    inputs.add_argument('--remote', action='store_true', help='leer wireless_remote, solo en shadow; sustituye --command')
    args = parser.parse_args()
    if args.remote and args.mode != 'shadow':
        parser.error('--remote solo está disponible en shadow')
    if args.iface == 'lo' or args.iface not in dict(socket.if_nameindex()).values():
        parser.error('Select the Go2 Ethernet interface')
    if not 0 < args.seconds <= (.5 if args.mode == 'bench' else 60.):
        parser.error('Bench duration is limited to 0.5 s, observation to 60 s')
    if (args.mode == 'bench') != (args.bench_profile is not None):
        parser.error('Bench requires a verified --bench-profile')
    if args.commands_stdin and args.mode != 'shadow':
        parser.error('--commands-stdin solo está disponible en shadow')
    config = load_profile(args.bench_profile, args.iface) if args.bench_profile else None
    actor = A2Policy(args.policy_update) if args.mode != 'observe' else None
    signal.signal(signal.SIGTERM, stop_on_signal)
    ChannelFactoryInitialize(0, args.iface)
    rx = Latest(STATE_TOPIC, LowState_)
    if args.remote:
        return capture_remote(args, rx, actor)
    encoder = MotorCommands()
    rx.wait(lambda *_: True, 4.)
    if args.mode == 'bench':
        bench(args, rx, encoder, actor, config)
    else:
        capture(args, rx, encoder, actor)


if __name__ == '__main__':
    raise SystemExit(main())
