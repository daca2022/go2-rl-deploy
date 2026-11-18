"""Unitree low-level DDS IDL shared by simulator and bench programs."""
from threading import Condition
import time

import numpy as np
from cyclonedds.qos import Policy, Qos
from cyclonedds.util import duration
from unitree_sdk2py.core.channel import ChannelFactory, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.utils.crc import CRC

from a2_policy import SDK_IDS

STATE_TOPIC = 'rt/lowstate'
COMMAND_TOPIC = 'rt/lowcmd'
SIM_DOMAIN = 19


class Latest:
    """Keep one receive-time-stamped sample without a user-space queue."""
    def __init__(self, topic, msg_type):
        self.condition = Condition()
        self.value = None
        self.subscriber = ChannelSubscriber(topic, msg_type)
        self.subscriber.Init(self.receive)

    def receive(self, msg):
        with self.condition:
            self.value = msg, time.monotonic()
            self.condition.notify_all()

    def wait(self, predicate, timeout):
        with self.condition:
            matched = self.condition.wait_for(
                lambda: self.value is not None and predicate(*self.value), timeout)
            if not matched:
                raise TimeoutError('DDS sample timeout')
            return self.value

    def fresh(self, max_age):
        msg, stamp = self.wait(lambda *_: True, 0.)
        if time.monotonic() - stamp > max_age:
            raise TimeoutError('DDS LowState is stale')
        return msg, stamp


def publisher(topic, msg_type):
    endpoint = ChannelPublisher(topic, msg_type)
    endpoint.Init()
    return endpoint


def bounded_command_publisher():
    # Unitree's public Write(timeout=...) polls discovery in 100 ms increments.
    # Bound DDS backpressure itself and use the no-wait SDK write call.
    endpoint = ChannelFactory().CreateChannel(COMMAND_TOPIC, LowCmd_)
    endpoint.SetWriter(Qos(Policy.Reliability.Reliable(max_blocking_time=duration(milliseconds=2)),
                           Policy.History.KeepLast(1)))
    return endpoint


def state_joints(msg):
    motors = [msg.motor_state[i] for i in SDK_IDS]
    return np.array([m.q for m in motors]), np.array([m.dq for m in motors])


class MotorCommands:
    def __init__(self):
        self.crc = CRC()
        self.message = unitree_go_msg_dds__LowCmd_()
        self.message.head = [0xFE, 0xEF]
        self.message.level_flag = 0xFF
        for motor in self.message.motor_cmd:
            motor.mode = 1
            motor.q = 2.146e9
            motor.dq = 16000.
            motor.kp = motor.kd = motor.tau = 0.

    def fill(self, q, kp, kd, *, sim_tick=0):
        self.message.reserve = sim_tick
        for i, pos, pgain, dgain in zip(SDK_IDS, q, kp, kd, strict=True):
            motor = self.message.motor_cmd[i]
            motor.q, motor.kp, motor.kd = float(pos), float(pgain), float(dgain)
            motor.dq = 0.
        self.message.crc = self.crc.Crc(self.message)
        return self.message
