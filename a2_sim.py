"""Run the compiled P0 model and A2 as separate DDS endpoints over loopback."""
import argparse
import csv
from contextlib import nullcontext
import json
import math
from pathlib import Path
import time

import mujoco
import numpy as np
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_

from a2_dds import CRC, COMMAND_TOPIC, STATE_TOPIC, SIM_DOMAIN, Latest, LowCmd_, LowState_, MotorCommands, bounded_command_publisher, publisher, state_joints
from a2_policy import A2Policy, COMMANDS, JOINT_NAMES, KD, KP, MODEL, PERIOD, SDK_IDS, verified_file


def run_bridge(output, ticks, view):
    spec = json.loads((MODEL/'manifest.json').read_text())
    if spec['mujoco_version'] != mujoco.__version__:
        raise ValueError('Incorrect MuJoCo version for MJB')
    model = mujoco.MjModel.from_binary_path(str(verified_file(spec, 'go2-p0.mjb')))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, model.key('init_state').id)
    mujoco.mj_forward(model, data)
    joints = [model.joint(name).id for name in JOINT_NAMES]
    qids, vids = model.jnt_qposadr[joints], model.jnt_dofadr[joints]
    aids = [model.actuator(name).id for name in JOINT_NAMES]
    if not (np.array_equal(model.actuator_gainprm[aids, 0], KP)
            and np.array_equal(model.actuator_biasprm[aids, 2], -KD)):
        raise ValueError('P0 gains differ from compiled actuators')

    rx = Latest(COMMAND_TOPIC, LowCmd_)
    tx = publisher(STATE_TOPIC, LowState_)
    state = unitree_go_msg_dds__LowState_()
    crc = CRC()
    rotation = np.zeros(9)
    context = nullcontext(None)
    if view:
        from mujoco.viewer import launch_passive
        context = launch_passive(model, data)
    print('MuJoCo DDS listo en lo, dominio 19', flush=True)
    with output.open('x', newline='') as file, context as viewer:
        writer = csv.writer(file)
        writer.writerow(['tick', 't_s', 'vx_m_s', 'vy_m_s', 'yaw_rad_s', 'height_m', 'fall'])
        if viewer:
            with viewer.lock():
                viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
                viewer.cam.trackbodyid = model.body('robot/base_link').id
                viewer.cam.distance = 2.5
        for tick in range(1, ticks+1):
            if viewer is not None and not viewer.is_running():
                raise RuntimeError('Viewer closed before simulation finished')
            state.tick = tick
            state.imu_state.quaternion = data.qpos[3:7].tolist()
            state.imu_state.gyroscope = data.qvel[3:6].tolist()
            for index, q, dq in zip(SDK_IDS, data.qpos[qids], data.qvel[vids], strict=True):
                state.motor_state[index].q = float(q)
                state.motor_state[index].dq = float(dq)
            state.crc = crc.Crc(state)
            tx.Write(state)
            # Sequence tags are used on loopback only. A missing controller leaves physics paused.
            deadline = time.monotonic() + (30 if tick == 1 else 1)
            while True:
                try:
                    msg, _ = rx.wait(lambda m, _: m.reserve == tick, .1)
                    break
                except TimeoutError:
                    if time.monotonic() >= deadline:
                        raise
                    tx.Write(state)
            targets = [msg.motor_cmd[i].q for i in SDK_IDS]
            gains_p = [msg.motor_cmd[i].kp for i in SDK_IDS]
            gains_d = [msg.motor_cmd[i].kd for i in SDK_IDS]
            if (msg.crc != crc.Crc(msg) or not np.isfinite(targets).all()
                    or not np.array_equal(gains_p, KP) or not np.array_equal(gains_d, KD)):
                raise ValueError('Bad LowCmd CRC or P0 fields in simulation')
            lock = nullcontext() if viewer is None else viewer.lock()
            with lock:
                data.ctrl[aids] = targets
                for _ in range(spec['decimation']):
                    mujoco.mj_step(model, data)
                mujoco.mju_quat2Mat(rotation, data.qpos[3:7])
                velocity = rotation.reshape(3, 3).T @ data.qvel[:3]
                fell = data.qpos[2] < .16 or rotation[8] < .5
                writer.writerow([tick, round(data.time, 3), *velocity[:2], data.qvel[5],
                                 data.qpos[2], int(fell)])
                file.flush()
            if viewer is not None:
                viewer.sync()
                time.sleep(PERIOD)
            if fell:
                raise RuntimeError(f'Simulated fall at tick {tick}')
    print(json.dumps({'simulated_seconds':round(data.time,3), 'fall':False, 'dds_ticks':ticks}))


def run_policy(command, ticks):
    policy = A2Policy()
    rx = Latest(STATE_TOPIC, LowState_)
    tx = bounded_command_publisher()
    encoder = MotorCommands()
    for tick in range(1, ticks+1):
        msg, _ = rx.wait(lambda m, _: m.tick == tick, 30 if tick == 1 else 1)
        if msg.crc != encoder.crc.Crc(msg):
            raise ValueError('Bad simulation LowState CRC')
        q, dq = state_joints(msg)
        targets = policy.step(msg.imu_state.quaternion, msg.imu_state.gyroscope, q, dq, command)
        if not tx.Write(encoder.fill(targets, KP, KD, sim_tick=tick)):
            raise RuntimeError('DDS LowCmd write failed')
    print(json.dumps({'policy_ticks':policy.tick, 'last_target_rad':targets.tolist()}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=('bridge','policy'))
    parser.add_argument('--command', choices=COMMANDS, default='forward')
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--view', action='store_true')
    parser.add_argument('--ticks', type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.ticks <= 1000:
        parser.error('--ticks must be in 1..1000')
    if args.role == 'bridge' and args.csv is None:
        parser.error('--csv is required for bridge')
    ChannelFactoryInitialize(SIM_DOMAIN, 'lo')
    if args.role == 'bridge':
        run_bridge(args.csv, args.ticks, args.view)
    else:
        run_policy(COMMANDS[args.command], args.ticks)


if __name__ == '__main__':
    main()
