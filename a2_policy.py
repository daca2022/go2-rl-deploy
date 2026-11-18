"""Observation and action mapping shared by local and SDK replays."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

MODEL = Path(__file__).resolve().parent / 'model'
COMMANDS = {'forward': (.3, 0., 0.), 'reverse': (-.2, 0., 0.),
            'lateral': (0., .2, 0.), 'yaw': (0., 0., .3)}
# Unitree SDK LegID groups FR, FL, RR, RL. The actor uses FL, FR, RL, RR.
LEGS = ('FL', 'FR', 'RL', 'RR')
SDK_IDS = (3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8)
JOINT_NAMES = [f'robot/{leg}_{joint}_joint' for leg in LEGS for joint in ('hip', 'thigh', 'calf')]
KP = np.array([20., 20., 40.] * 4)
KD = np.array([1., 1., 2.] * 4)
SIM_TORQUE_LIMIT = np.array([23.5, 23.5, 45.] * 4)
SIM_JOINT_RANGE = np.array([
    [(-1.0472, 1.0472), (-1.5708 if leg[0] == 'F' else -.5236,
                       3.4907 if leg[0] == 'F' else 4.5379), (-2.7227, -.83776)]
    for leg in LEGS
]).reshape(12, 2)
PERIOD = .02


def verified_file(spec, name):
    path = MODEL / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != spec['files'][name]:
        raise ValueError(f'Model checksum mismatch: {name}')
    return path


def gravity_body(quat):
    w, x, y, z = quat
    return np.array([2*(w*y-x*z), -2*(y*z+w*x), 2*(x*x+y*y)-1.])


class A2Policy:
    def __init__(self):
        self.spec = json.loads((MODEL / 'manifest.json').read_text())
        if self.spec['joint_names'] != JOINT_NAMES:
            raise ValueError('Model joint order differs from the Unitree mapping')
        if self.spec['physics_dt'] * self.spec['decimation'] != PERIOD:
            raise ValueError('Unexpected policy period')
        torch.set_num_threads(1)
        path = verified_file(self.spec, 'a2-p0-u2000.ts')
        self.actor = torch.jit.load(str(path), map_location='cpu').eval()
        self.q0 = np.array(self.spec['q0'], dtype=np.float32)
        self.previous = np.zeros(12, dtype=np.float32)
        self.tick = 0
        self.reset()

    def reset(self):
        with torch.inference_mode():
            self.actor.reset()
        self.previous.fill(0.)
        self.tick = 0

    def step(self, quat, gyro, q, dq, command):
        quat = np.asarray(quat)
        if not np.isfinite(quat).all() or not .98 <= np.linalg.norm(quat) <= 1.02:
            raise ValueError('Invalid IMU quaternion')
        phase = 2 * np.pi * self.tick * PERIOD / .6
        obs = np.concatenate((gyro, gravity_body(quat), command, q-self.q0, dq,
                              self.previous, (np.sin(phase), np.cos(phase))))
        if obs.shape != (47,) or not np.isfinite(obs).all():
            raise ValueError('Invalid 47-element policy observation')
        with torch.inference_mode():
            action = self.actor(torch.tensor(obs, dtype=torch.float32).unsqueeze(0))[0].numpy()
        if action.shape != (12,) or not np.isfinite(action).all():
            raise ValueError('Invalid actor output')
        self.previous = action
        self.tick += 1
        return self.q0 + self.spec['scale'] * action
