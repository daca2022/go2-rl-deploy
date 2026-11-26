"""Ensayo de activación del alumno GRU desde telemetría archivada, solo MuJoCo."""
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

from a2_policy import A2Policy, JOINT_NAMES, KD, KP, LEGS, PERIOD
from teleop_mujoco import Simulation

ZERO = (0., 0., 0.)
REFERENCE_DEG = {"RR_hip": 18.63, "RL_thigh": 15.19, "FL_hip": -14.21}
SCHEDULE = [
    ("initial_zero", 4, ZERO), ("forward", 3, (.3, 0, 0)),
    ("stop_1", 3, ZERO), ("reverse", 3, (-.2, 0, 0)),
    ("stop_2", 3, ZERO), ("left", 3, (0, .2, 0)),
    ("stop_3", 3, ZERO), ("right", 3, (0, -.2, 0)),
    ("stop_4", 3, ZERO), ("turn_left", 3, (0, 0, .3)),
    ("stop_5", 3, ZERO), ("turn_right", 3, (0, 0, -.3)),
    ("stop_6", 3, ZERO), ("resume_forward", 3, (.3, 0, 0)),
    ("final_stop", 3, ZERO),
]


def read_capture(path):
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    times = np.array([float(r["pc_time_s"]) for r in rows])
    if len(times) < 2 or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("Se requieren tiempos crecientes y finitos")
    if len({r["dds_tick"] for r in rows}) != len(rows):
        raise ValueError("La captura contiene ticks DDS repetidos")
    def vector(name, size):
        data = np.array([json.loads(r[name]) for r in rows], dtype=float)
        if data.shape != (len(rows), size) or not np.isfinite(data).all():
            raise ValueError(f"Vector inválido: {name}")
        return data
    q = vector("q_sdk_in_actor_order_rad", 12)
    dq = vector("dq_sdk_in_actor_order_rad_s", 12)
    quat = vector("imu_wxyz", 4)
    gyro = vector("gyro_rad_s", 3)
    if np.any(np.abs(np.linalg.norm(quat, axis=1) - 1) > .02):
        raise ValueError("Cuaterniones fuera de rango")
    if times[0] > 25 or times[-1] < 25 or times[-1]-times[0] < 5:
        raise ValueError("La captura debe abarcar el segundo 25 y cinco segundos finales")
    last = times >= times[-1] - 5
    # Keep quaternion signs aligned before computing a normalized component median.
    tail = quat[last].copy()
    tail[tail @ tail[-1] < 0] *= -1
    orientation = np.median(tail, axis=0)
    orientation /= np.linalg.norm(orientation)
    row = int(np.argmin(np.abs(times - 25.)))
    actor = A2Policy("student")
    target = actor.step(quat[row], gyro[row], q[row], dq[row], ZERO)
    delta_deg = np.degrees(target - q[row])
    reference = {
        name: {"expected_deg": value, "computed_deg": float(delta_deg[JOINT_NAMES.index(f"robot/{name}_joint")]),
               "error_deg": float(delta_deg[JOINT_NAMES.index(f"robot/{name}_joint")] - value)}
        for name, value in REFERENCE_DEG.items()
    }
    summary = {
        "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "samples": len(rows), "duration_s": float(times[-1]-times[0]),
        "standing_window_samples": int(last.sum()), "replay_row_s": float(times[row]),
        "input_order": JOINT_NAMES, "units": "rad, rad/s, wxyz",
        "joint_median_rad": np.median(q[last], axis=0).tolist(),
        "joint_span_last5_rad": np.ptp(q[last], axis=0).tolist(),
        "quaternion_median_wxyz": orientation.tolist(),
        "offline_first_action_delta_deg": delta_deg.tolist(),
        "offline_reference": reference,
        "offline_reference_matches_0_05_deg": all(abs(v["error_deg"]) <= .05 for v in reference.values()),
        "physical_mapping": "SDK actor order as archived; signs/zeros assumed identical for simulation only",
    }
    return np.array(summary["joint_median_rad"]), orientation, summary


class StandingSimulation(Simulation):
    def __init__(self, q, quat):
        super().__init__()
        m, d = self.model, self.data
        self.feet = {m.geom(f"robot/{leg}_foot_collision").id: leg for leg in LEGS}
        self.base = m.body("robot/base_link").id
        self.terrain = m.body("terrain").id
        if (not np.allclose(m.opt.timestep, self.actor.spec["physics_dt"])
                or not np.allclose(m.actuator_gainprm[self.aids, 0], KP)
                or not np.allclose(m.actuator_biasprm[self.aids, 2], -KD)):
            raise ValueError("La planta P0 no coincide con el manifiesto")
        joint_ids = [m.joint(name).id for name in JOINT_NAMES]
        expected_axes = np.tile([[1., 0, 0], [0, 1., 0], [0, 1., 0]], (4, 1))
        if (not np.allclose(m.jnt_axis[joint_ids], expected_axes)
                or not np.array_equal(m.actuator_trnid[self.aids, 0], joint_ids)
                or np.any(q < m.jnt_range[joint_ids, 0]) or np.any(q > m.jnt_range[joint_ids, 1])):
            raise ValueError("Ejes, actuadores o límites articulares inconsistentes")
        if int(m.geom_type[0]) != int(mujoco.mjtGeom.mjGEOM_PLANE) or not np.allclose(d.geom_xmat[0].reshape(3,3)[:,2], [0,0,1]):
            raise ValueError("Se requiere el plano horizontal P0")
        # Root translation/velocity are absent in the recording. Place the lowest sole on the plane.
        d.qpos[:3] = 0.
        d.qpos[3:7] = quat
        d.qpos[self.qids] = q
        d.qvel[:] = 0.
        d.ctrl[self.aids] = q
        mujoco.mj_forward(m, d)
        foot_ids = list(self.feet)
        bottoms = d.geom_xpos[foot_ids, 2] - m.geom_size[foot_ids, 0]
        d.qpos[2] = d.geom_xpos[0, 2] - min(bottoms)
        mujoco.mj_forward(m, d)
        self.initial_q = q.copy()
        self.reconstruction = {
            "height_m": float(d.qpos[2]),
            "foot_clearance_m": dict(zip(LEGS, (bottoms - min(bottoms)).tolist())),
            "joint_axes": expected_axes.tolist(),
            "base_velocity_assumption": "zero; measured base translation and velocity unavailable",
            "contacts": self.contacts(),
            "all_four_feet_initially_in_contact": len(self.contacts()["feet"]) == 4,
        }

    def contacts(self):
        feet = set()
        illegal = set()
        for c in self.data.contact:
            for ground, robot in ((c.geom1, c.geom2), (c.geom2, c.geom1)):
                if self.model.geom_bodyid[ground] != self.terrain:
                    continue
                if robot in self.feet:
                    feet.add(self.feet[robot])
                elif self.model.geom_bodyid[robot] >= self.base:
                    illegal.add(self.model.geom(robot).name)
        return {"feet": [leg for leg in LEGS if leg in feet],
                "nonfoot": sorted(illegal),
                "trunk": any(name.startswith("robot/base") for name in illegal)}

    def tilt_deg(self):
        return float(np.degrees(np.arccos(np.clip(self.orientation()[2, 2], -1, 1))))

    def physics(self, target):
        self.data.ctrl[self.aids] = target
        nonfoot = set()
        trunk = False
        fallen = False
        tilt = 0.
        for _ in range(self.actor.spec["decimation"]):
            mujoco.mj_step(self.model, self.data)
            if not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all():
                raise RuntimeError("MuJoCo generó estado no finito")
            contacts = self.contacts()
            nonfoot.update(contacts["nonfoot"])
            trunk |= contacts["trunk"]
            tilt = max(tilt, self.tilt_deg())
            fallen |= self.data.qpos[2] < .16 or tilt > 60 or trunk
        return fallen, trunk, sorted(nonfoot), tilt


def yaw(rotation):
    return math.atan2(rotation[1, 0], rotation[0, 0])


def settle_probe(q, quat, output):
    sim = StandingSimulation(q, quat)
    initial = sim.reconstruction
    peak = 0.
    contacts = set()
    failed = False
    with output.open("x", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "height_m", "joint_error_max_deg", "feet", "nonfoot", "fall"])
        for _ in range(round(1. / PERIOD)):
            fall, _, nonfoot, _ = sim.physics(q)
            error = float(np.max(np.abs(np.degrees(sim.data.qpos[sim.qids]-q))))
            peak = max(peak, error)
            contacts.update(nonfoot)
            failed |= fall
            writer.writerow([sim.data.time, sim.data.qpos[2], error, "|".join(sim.contacts()["feet"]),
                             "|".join(nonfoot), int(fall)])
            if fall:
                break
    end = sim.contacts()
    return {"initial": initial, "duration_s": sim.data.time, "final_height_m": float(sim.data.qpos[2]),
            "final_contacts": end, "nonfoot_during_settle": sorted(contacts), "fall": failed,
            "final_joint_delta_deg": np.degrees(sim.data.qpos[sim.qids]-q).tolist(),
            "max_joint_deviation_deg": peak,
            "physically_consistent_fixed_pose": not failed and not contacts and len(end["feet"]) == 4 and peak <= 5.,
            "criterion": "1 s fixed measured target; four feet at end, no nonfoot contact, <=5 deg deviation"}


def mean_neutral_target(q, quat, blend):
    """Build a simulation-only candidate from the last second of neutral closed-loop motion."""
    sim = StandingSimulation(q, quat)
    targets = []
    for tick in range(round(4. / PERIOD)):
        d = sim.data
        raw = sim.actor.step(d.qpos[3:7], d.qvel[3:6], d.qpos[sim.qids], d.qvel[sim.vids], ZERO)
        weight = min(1., tick * PERIOD / blend)
        fall, _, illegal, _ = sim.physics((1.-weight)*q + weight*raw)
        if fall or illegal:
            raise ValueError("No se pudo generar una referencia neutra sin contactos ilegales")
        if tick >= round(3. / PERIOD):
            targets.append(raw)
    return np.mean(targets, axis=0)


def trial(q, quat, output, variant, blend, view):
    sim = StandingSimulation(q, quat)
    d = sim.data
    previous = q.copy()
    wait_target = mean_neutral_target(q, quat, blend) if variant == "wait-mean" else sim.actor.q0
    mode = "policy"
    transitions = []
    blend_origin, blend_start = q.copy(), 0.
    stats = []
    max_tilt, max_jump = 0., 0.
    trunk = False
    nonfoot_all = set()
    first = None
    status = "complete"
    tick = 0
    wall_start = time.perf_counter()
    if view:
        from mujoco.viewer import launch_passive
        context = launch_passive(sim.model, d)
    else:
        context = nullcontext(None)
    with output.open("x", newline="") as f, context as viewer:
        writer = csv.writer(f)
        writer.writerow(["t_s","maneuver","controller","cmd_vx","cmd_vy","cmd_yaw","x_m","y_m","height_m",
                         "vx_body_m_s","vy_body_m_s","yaw_rate_rad_s","tilt_deg","feet","nonfoot","trunk","fall",
                         "raw_target_rad","applied_target_rad","q_rad","target_step_max_deg","compute_ms"])
        if viewer is not None:
            with viewer.lock():
                viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
                viewer.cam.trackbodyid = sim.base
                viewer.cam.distance = 2.0
        for label, seconds, command in SCHEDULE:
            rotation = sim.orientation().copy()
            origin = d.qpos[:2].copy()
            y0 = yaw(rotation)
            last_yaw = y0
            turn = 0.
            velocities, speeds, weights, masks, motion = [], [], [], [], []
            completed = 0
            stop_jump = 0.
            phase_nonfoot = set()
            phase_trunk = False
            for j in range(round(seconds / PERIOD)):
                if viewer is not None and not viewer.is_running():
                    status = "viewer_closed"
                    break
                before = time.perf_counter()
                if variant in ("wait", "wait-mean"):
                    # In simulation only, wait for a low-speed, upright, supported state before returning to fixed nominal P0.
                    if command == ZERO and mode == "policy" and j*PERIOD >= .5 and np.linalg.norm(d.qvel[:2]) <= .08 and sim.tilt_deg() <= 15 and len(sim.contacts()["feet"]) >= 3:
                        mode = "wait"
                        blend_origin, blend_start = previous.copy(), tick*PERIOD
                        transitions.append({"t_s": tick*PERIOD, "to": mode, "reason": "centered >=0.5 s, slow, upright, >=3 feet"})
                    elif command != ZERO and mode == "wait":
                        mode = "policy"
                        blend_origin, blend_start = previous.copy(), tick*PERIOD
                        transitions.append({"t_s": tick*PERIOD, "to": mode, "reason": "nonzero command"})
                raw = sim.actor.step(d.qpos[3:7], d.qvel[3:6], d.qpos[sim.qids], d.qvel[sim.vids], command)
                target = wait_target if mode == "wait" else raw
                weight = 1. if variant == "direct" else min(1., (tick*PERIOD-blend_start)/blend)
                applied = (1.-weight)*blend_origin + weight*target
                jump = float(np.max(np.abs(np.degrees(applied-previous))))
                if first is None:
                    first = {"raw_delta_deg": np.degrees(raw-q).tolist(), "applied_delta_deg": np.degrees(applied-q).tolist()}
                previous = applied.copy()
                max_jump = max(max_jump, jump)
                stop_jump = max(stop_jump, jump)
                with viewer.lock() if viewer is not None else nullcontext():
                    fell, body, illegal, tilt = sim.physics(applied)
                max_tilt = max(max_tilt, tilt)
                trunk |= body
                nonfoot_all.update(illegal)
                phase_nonfoot.update(illegal)
                phase_trunk |= body
                r = sim.orientation().copy()
                v = r.T @ d.qvel[:3]
                angle = yaw(r)
                turn += math.atan2(math.sin(angle-last_yaw), math.cos(angle-last_yaw))
                last_yaw = angle
                contacts = sim.contacts()
                mask = "|".join(contacts["feet"])
                masks.append(mask)
                speed = float(np.linalg.norm(v[:2]))
                velocities.append([float(v[0]), float(v[1]), float(d.qvel[5])])
                speeds.append(speed)
                weights.append(mode == "wait")
                motion.append(float(np.linalg.norm(d.qvel[sim.vids])))
                compute_ms = (time.perf_counter()-before)*1000
                writer.writerow([round(d.time, 6),label,mode,*command,*d.qpos[:3],*v[:2],d.qvel[5],tilt,
                                 mask,"|".join(illegal),int(body),int(fell),json.dumps(raw.tolist()),
                                 json.dumps(applied.tolist()),json.dumps(d.qpos[sim.qids].tolist()),jump,compute_ms])
                tick += 1
                completed += 1
                if viewer is not None:
                    viewer.sync()
                    time.sleep(max(0., PERIOD - (time.perf_counter()-before)))
                if fell:
                    status = "fall"
                    break
            if completed:
                heading = np.array([[math.cos(y0), -math.sin(y0)], [math.sin(y0), math.cos(y0)]])
                displacement = heading.T @ (d.qpos[:2]-origin)
                avg = np.mean(velocities, axis=0)
                signed = float(turn if command[2] else displacement[0] if command[0] else displacement[1])
                expected = next((x for x in command if x != 0), 0)
                final = velocities[-min(completed, round(1/PERIOD)):]
                final_speed = float(np.mean(np.linalg.norm(np.array(final)[:,:2],axis=1)))
                final_motion = float(np.mean(motion[-len(final):]))
                stats.append({"maneuver":label,"duration_s":completed*PERIOD,"command":command,
                    "local_displacement_m":displacement.tolist(),"yaw_delta_deg":math.degrees(turn),
                    "mean_body_velocity":avg.tolist(),"mean_planar_speed_m_s":float(np.mean(speeds)),
                    "final_1s_mean_planar_speed_m_s":final_speed,"final_1s_mean_joint_speed_norm_rad_s":final_motion,
                    "contact_pattern_changes":sum(a!=b for a,b in zip(masks,masks[1:])),
                    "nonfoot_contacts":sorted(phase_nonfoot),"trunk_contact":phase_trunk,
                    "fixed_wait_fraction":float(np.mean(weights)),
                    "max_target_step_deg":stop_jump,
                    "direction_observed":None if not expected else bool(signed*np.sign(expected) > (.05 if command[2] else .02)),
                    "zero_settled":None if expected else bool(final_speed <= .03 and np.mean(np.abs(np.array(final)[:,2])) <= .05 and final_motion <= .3)})
            if status != "complete":
                break
    with output.open(newline="") as f:
        compute = [float(row["compute_ms"]) for row in csv.DictReader(f)]
    return {"variant":variant,"blend_s":0. if variant == "direct" else blend,
            "status":status,"duration_s":tick*PERIOD,"samples":tick,"simulated_hz":1/PERIOD,
            "wall_elapsed_s":time.perf_counter()-wall_start,
            "compute_ms_median":float(np.median(compute)) if compute else None,
            "compute_ms_p95":float(np.percentile(compute,95)) if compute else None,
            "max_tilt_deg":max_tilt,"trunk_contact":trunk,"nonfoot_contacts":sorted(nonfoot_all),
            "first_activation":first,"max_target_step_deg":max_jump,
            "fixed_wait_target_rad":wait_target.tolist() if variant in ("wait", "wait-mean") else None,
            "transitions":transitions,"maneuvers":stats,
            "completed_without_nonfoot_contact": status == "complete" and not nonfoot_all,
            "all_requested_directions_observed": status == "complete" and all(
                item["direction_observed"] for item in stats if item["direction_observed"] is not None),
            "all_zero_segments_settled": status == "complete" and all(
                item["zero_settled"] for item in stats if item["zero_settled"] is not None),
            "criteria": {"direction_min_displacement_m": .02, "direction_min_yaw_rad": .05,
                         "zero_last_second_planar_speed_m_s": .03, "zero_last_second_abs_yaw_rate_rad_s": .05,
                         "zero_last_second_joint_speed_norm_rad_s": .3},
            "reconstruction":sim.reconstruction}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path, help="CSV archivado del modo observe")
    parser.add_argument("--out", required=True, type=Path, help="Directorio nuevo de resultados")
    parser.add_argument("--variant", choices=["all", "direct", "ramp", "wait", "wait-mean"], default="all")
    parser.add_argument("--blend-s", type=float, default=.5, help="Duración de mezcla para ramp y wait")
    parser.add_argument("--view", action="store_true", help="Mostrar cada ensayo en tiempo real")
    args = parser.parse_args()
    if not math.isfinite(args.blend_s) or not PERIOD <= args.blend_s <= 5:
        parser.error("--blend-s debe estar entre 0.02 y 5 segundos")
    q, quat, data = read_capture(args.csv)
    args.out.mkdir(parents=True, exist_ok=False)
    result = {"scope":"simulation_only", "mujoco_version":mujoco.__version__, "capture":data,
              "fixed_pose_settle":settle_probe(q, quat, args.out/"settle.csv"), "trials":{}}
    variants = ("direct", "ramp", "wait", "wait-mean") if args.variant == "all" else (args.variant,)
    for variant in variants:
        measured = trial(q, quat, args.out/f"{variant}.csv", variant, args.blend_s, args.view)
        result["trials"][variant] = measured
        (args.out/f"{variant}.json").write_text(json.dumps(measured, indent=2)+"\n")
        print(json.dumps({k:measured[k] for k in ("variant","status","duration_s","max_tilt_deg","trunk_contact")}),flush=True)
    (args.out/"summary.json").write_text(json.dumps(result, indent=2)+"\n")
    print(f"Resumen: {args.out/'summary.json'}")


if __name__ == "__main__":
    main()
