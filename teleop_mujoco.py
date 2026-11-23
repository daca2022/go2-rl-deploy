"""Teleoperate the GRU in MuJoCo or move to a measured local XY target."""

import argparse
from contextlib import nullcontext
import csv
import json
import math
from pathlib import Path
import time

import mujoco
import numpy as np

from a2_policy import A2Policy, PERIOD, verified_file
from teleop_input import CommandLease, KeyboardWindow, STOP, VELOCITIES

ARRIVAL_M = .02
SETTLE_S = .6


class Simulation:
    def __init__(self):
        self.actor = A2Policy("student")
        spec = self.actor.spec
        if mujoco.__version__ != spec["mujoco_version"]:
            raise ValueError("Instala la versión de MuJoCo indicada en requirements-sim.txt")
        self.model = mujoco.MjModel.from_binary_path(str(verified_file(spec, "go2-p0.mjb")))
        self.data = mujoco.MjData(self.model)
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.model.key("init_state").id)
        mujoco.mj_forward(self.model, self.data)
        joint_ids = [self.model.joint(name).id for name in spec["joint_names"]]
        self.qids = self.model.jnt_qposadr[joint_ids]
        self.vids = self.model.jnt_dofadr[joint_ids]
        self.aids = [self.model.actuator(name).id for name in spec["joint_names"]]
        self.rotation = np.empty(9)

    def orientation(self):
        mujoco.mju_quat2Mat(self.rotation, self.data.qpos[3:7])
        return self.rotation.reshape(3, 3)

    def step(self, command):
        d = self.data
        d.ctrl[self.aids] = self.actor.step(d.qpos[3:7], d.qvel[3:6], d.qpos[self.qids], d.qvel[self.vids], command)
        for _ in range(self.actor.spec["decimation"]):
            mujoco.mj_step(self.model, d)
        if not np.isfinite(d.qpos).all() or not np.isfinite(d.qvel).all():
            raise RuntimeError("MuJoCo generó un estado no finito")
        return bool(d.qpos[2] < .16 or self.orientation()[2, 2] < .5)


class Goal:
    def __init__(self, target):
        self.target = np.asarray(target)
        self.stopping = False
        self.stable_for = 0.
        self.position_integral = np.zeros(2)

    def error(self, sim):
        return float(np.linalg.norm(self.target - sim.data.qpos[:2]))

    def command(self, sim):
        error = self.target - sim.data.qpos[:2]
        distance = float(np.linalg.norm(error))
        speed = float(np.linalg.norm(sim.data.qvel[:2]))
        if distance <= ARRIVAL_M * .75 and speed <= .035:
            self.stopping = True
        # Reacquire only when the body drifts past the acceptance radius.
        if distance > ARRIVAL_M:
            self.stopping = False
        if self.stopping:
            return VELOCITIES[STOP]
        self.position_integral = np.clip(self.position_integral + error * PERIOD, -.12, .12)
        velocity = 2.4 * error + 1.1 * self.position_integral - .8 * sim.data.qvel[:2]
        body_velocity = sim.orientation().T @ np.r_[velocity, 0.]
        vx, vy = np.clip(body_velocity[:2], [-.20, -.20], [.30, .20])
        return (float(vx), float(vy), 0.)

    def complete(self, sim):
        if self.stopping and self.error(sim) <= ARRIVAL_M and np.linalg.norm(sim.data.qvel[:2]) <= .06:
            self.stable_for += PERIOD
        else:
            self.stable_for = 0.
        return self.stable_for >= SETTLE_S


def demonstration(lease, elapsed):
    # The first move is released explicitly. The second loses its input stream.
    if elapsed < 1.:
        lease.renew(STOP, elapsed)
    elif elapsed < 3.:
        lease.renew("w", elapsed)
    elif elapsed < 5.:
        lease.renew(STOP, elapsed)
    elif elapsed < 7.:
        lease.renew("s", elapsed)
    return lease.sample(elapsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--distance-m", type=float, help="desplazamiento firmado en el eje inicial de avance")
    mode.add_argument("--goal", type=float, nargs=2, metavar=("X", "Y"), help="destino relativo en el marco inicial")
    mode.add_argument("--demo", action="store_true", help="prueba de avance, liberación y pérdida de entrada")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--seconds", type=float, default=30.)
    parser.add_argument("--csv", required=True, type=Path)
    args = parser.parse_args()
    position = (args.distance_m, 0.) if args.distance_m is not None else args.goal
    manual = position is None and not args.demo
    if not 1. <= args.seconds <= 120.:
        parser.error("--seconds debe estar entre 1 y 120")
    if manual and args.headless:
        parser.error("Usa el visor para teleoperar o selecciona --demo en modo headless")
    if position is not None and (not all(map(math.isfinite, position)) or not .05 <= math.hypot(*position) <= 1.):
        parser.error("El destino debe quedar a una distancia de 0.05 a 1 m")
    sim = Simulation()
    origin = sim.data.qpos[:2].copy()
    goal = None if position is None else Goal(origin + (sim.orientation() @ np.r_[position, 0.])[:2])
    if args.headless:
        viewer_context = nullcontext(None)
    else:
        from mujoco.viewer import launch_passive

        viewer_context = launch_passive(sim.model, sim.data)
    keyboard = KeyboardWindow("Go2 · mando de MuJoCo") if manual else None
    lease = CommandLease()
    status = "time_limit"
    try:
        with args.csv.open("x", newline="") as file, viewer_context as viewer:
            csvlog = csv.writer(file)
            csvlog.writerow(("t_s", "cmd_vx", "cmd_vy", "cmd_yaw", "dx_m", "dy_m", "speed_m_s", "error_m", "fall"))
            if viewer is not None:
                with viewer.lock():
                    viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
                    viewer.cam.trackbodyid = sim.model.body("robot/base_link").id
                    viewer.cam.distance = 2.
            for _ in range(round(args.seconds / PERIOD)):
                if viewer is not None and not viewer.is_running():
                    status = "viewer_closed"
                    break
                started = time.monotonic()
                if keyboard is not None:
                    key = keyboard.poll()
                    if not keyboard.running:
                        status = "keyboard_closed"
                        break
                    lease.renew(key, started)
                    command = VELOCITIES[lease.sample(time.monotonic())]
                elif goal is not None:
                    command = goal.command(sim)
                else:
                    command = VELOCITIES[demonstration(lease, sim.data.time)]
                with viewer.lock() if viewer is not None else nullcontext():
                    fell = sim.step(command)
                error = None if goal is None else goal.error(sim)
                csvlog.writerow((round(sim.data.time, 3), *command, *(sim.data.qpos[:2] - origin),
                                 np.linalg.norm(sim.data.qvel[:2]), error, int(fell)))
                if viewer is not None:
                    viewer.sync()
                    time.sleep(max(0., PERIOD - (time.monotonic() - started)))
                if fell:
                    status = "fall"
                    break
                if goal is not None and goal.complete(sim):
                    status = "goal_reached"
                    break
    finally:
        if keyboard is not None:
            keyboard.destroy()
    print(json.dumps({"status": status, "simulated_s": round(sim.data.time, 3),
                      "displacement_m": (sim.data.qpos[:2] - origin).tolist(),
                      "goal_error_m": None if goal is None else goal.error(sim)}))
    return 1 if status == "fall" or (goal is not None and status != "goal_reached") else 0


if __name__ == "__main__":
    raise SystemExit(main())
