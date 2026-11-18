"""Replay the frozen A2/P0 actor on CPU and save commanded and measured motion."""
import argparse
from contextlib import nullcontext
import csv
import hashlib
import json
import math
from pathlib import Path
import time

import mujoco
import numpy as np
import torch

COMMANDS = {'forward': (.3, 0., 0.), 'reverse': (-.2, 0., 0.),
            'lateral': (0., .2, 0.), 'yaw': (0., 0., .3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=COMMANDS)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--view', action='store_true')
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent / 'model'
    spec = json.loads((bundle / 'manifest.json').read_text())
    for name, expected in spec['files'].items():
        if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != expected:
            raise SystemExit(f'Checksum incorrecto: {name}')
    if mujoco.__version__ != spec['mujoco_version']:
        raise SystemExit('Instala la versión de MuJoCo indicada en requirements-sim.txt')

    torch.set_num_threads(1)
    policy = torch.jit.load(str(bundle / 'a2-p0-u2000.ts'), map_location='cpu').eval()
    model = mujoco.MjModel.from_binary_path(str(bundle / 'go2-p0.mjb'))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, model.key('init_state').id)
    mujoco.mj_forward(model, data)
    ids = [model.joint(name).id for name in spec['joint_names']]
    qids, vids = model.jnt_qposadr[ids], model.jnt_dofadr[ids]
    aids = [model.actuator(name).id for name in spec['joint_names']]
    q0 = np.array(spec['q0'], dtype=np.float32)
    previous = np.zeros(12, dtype=np.float32)
    command = COMMANDS[args.command]
    rotation = np.empty(9)
    dt = spec['physics_dt'] * spec['decimation']

    context = nullcontext(None)
    if args.view:
        from mujoco.viewer import launch_passive
        context = launch_passive(model, data)
    errors = []
    status = 'viewer_closed'
    with args.csv.open('x', newline='') as file, context as viewer, torch.inference_mode():
        writer = csv.writer(file)
        writer.writerow(['t_s', 'cmd_vx_m_s', 'cmd_vy_m_s', 'cmd_yaw_rad_s',
                         'vx_m_s', 'vy_m_s', 'yaw_rad_s', 'base_height_m', 'fall_diagnostic'])
        policy.reset()
        if viewer is not None:
            viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
            viewer.cam.trackbodyid = model.body('robot/base_link').id
            viewer.cam.distance = 2.5
        for tick in range(1000):
            start = time.monotonic()
            if viewer is not None and not viewer.is_running():
                break
            mujoco.mju_quat2Mat(rotation, data.qpos[3:7])
            gravity = -rotation.reshape(3, 3)[2]
            phase = 2 * math.pi * tick * dt / .6
            obs = np.concatenate((data.qvel[3:6], gravity, command, data.qpos[qids]-q0,
                                  data.qvel[vids], previous, (math.sin(phase), math.cos(phase))))
            previous = policy(torch.tensor(obs, dtype=torch.float32).unsqueeze(0))[0].numpy()
            if not np.isfinite(previous).all():
                raise RuntimeError('Salida de política inválida')
            data.ctrl[aids] = q0 + spec['scale'] * previous
            for _ in range(spec['decimation']):
                mujoco.mj_step(model, data)
            mujoco.mju_quat2Mat(rotation, data.qpos[3:7])
            vx, vy, _ = rotation.reshape(3, 3).T @ data.qvel[:3]
            errors.append((vx-command[0])**2+(vy-command[1])**2)
            fell = bool(data.qpos[2] < .16 or rotation[8] < .5)
            writer.writerow([round(data.time, 3), *command, vx, vy, data.qvel[5], data.qpos[2], int(fell)])
            if viewer is not None:
                viewer.sync()
                time.sleep(max(0., dt - (time.monotonic()-start)))
            if fell:
                status = 'fall_diagnostic'
                break
        else:
            status = '20s_completed'
    print(json.dumps({'status': status, 'samples': len(errors),
                      'rmse_xy_m_s': math.sqrt(sum(errors)/len(errors)) if errors else None}))


if __name__ == '__main__':
    main()
