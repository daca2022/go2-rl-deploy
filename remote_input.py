"""Decode Unitree wireless_remote for passive GRU shadow inference."""

from collections import Counter
from dataclasses import dataclass
import math
from statistics import median
import struct

AXES = ("lx", "rx", "ry", "ly")
BUTTONS = ("R1", "L1", "Start", "Select", "R2", "L2", "F1", "F3",
           "A", "B", "X", "Y", "Up", "Right", "Down", "Left")
DEADZONE = .08
ZERO = (0., 0., 0.)


@dataclass(frozen=True)
class RemoteSample:
    axes: tuple
    button_mask: int | None
    buttons: tuple
    command: tuple
    status: str
    payload_hex: str
    unchanged_ms: float


def normalized(value):
    magnitude = min(abs(value), 1.)
    if magnitude <= DEADZONE:
        return 0.
    return math.copysign((magnitude-DEADZONE)/(1.-DEADZONE), value)


class RemoteDecoder:
    """An unchanged payload can mean a steady stick OR stale radio data."""
    def __init__(self):
        self.previous = None
        self.changed_at = None

    def decode(self, payload, now):
        try:
            packet = bytes(payload)
        except (TypeError, ValueError, OverflowError):
            packet = b""
        if self.previous != packet:
            self.previous = packet
            self.changed_at = now
        unchanged = (now-self.changed_at)*1000
        if len(packet) != 40:
            return RemoteSample((None,)*4, None, (), ZERO, "invalid_length", packet.hex(), unchanged)
        # SDK2 Python wireless_controller example: little-endian floats and bitmask.
        axes = tuple(struct.unpack_from("<f", packet, offset)[0] for offset in (4, 8, 12, 20))
        mask = struct.unpack_from("<H", packet, 2)[0]
        buttons = tuple(name for i, name in enumerate(BUTTONS) if mask & (1 << i))
        if any(not math.isfinite(value) or abs(value)>1.05 for value in axes):
            status, command = "invalid_axes", ZERO
        elif not any(packet):
            status, command = "all_zero_payload_link_unknown", ZERO
        else:
            lx, rx, _, ly = (normalized(value) for value in axes)
            vx = ly * (.3 if ly >= 0 else .2)
            command = (vx, -.2*lx, -.3*rx)
            status = "centered_axes_link_unknown" if all(abs(value)<=DEADZONE for value in axes) else "active_axes_link_unknown"
        return RemoteSample(axes, mask, buttons, command, status, packet.hex(), unchanged)


class RemoteStatistics:
    """Summarize the observed range and isolated deflections, without claiming RF validity."""
    def __init__(self):
        self.valid_axes = []
        self.centered_axes = []
        self.statuses = Counter()
        self.isolated = {axis: {"positive":0, "negative":0} for axis in AXES}
        self.max_unchanged_ms = 0.

    def add(self, sample):
        self.statuses[sample.status] += 1
        self.max_unchanged_ms = max(self.max_unchanged_ms, sample.unchanged_ms)
        if sample.status not in ("centered_axes_link_unknown", "active_axes_link_unknown"):
            return
        self.valid_axes.append(sample.axes)
        if sample.status == "centered_axes_link_unknown":
            self.centered_axes.append(sample.axes)
        active = [(name,value) for name,value in zip(AXES, sample.axes) if abs(value)>DEADZONE]
        if len(active)==1:
            name,value = active[0]
            self.isolated[name]["positive" if value>0 else "negative"] += 1

    def summary(self):
        ranges = {}
        for i,name in enumerate(AXES):
            values = [row[i] for row in self.valid_axes]
            centered = [row[i] for row in self.centered_axes]
            ranges[name] = {
                "min":min(values) if values else None,
                "max":max(values) if values else None,
                "center_median":median(centered) if centered else None,
                "isolated_samples":self.isolated[name],
            }
        return {"payload_status_counts":dict(self.statuses), "axes":ranges,
                "max_unchanged_payload_ms":self.max_unchanged_ms,
                "radio_link_verified":False}
