"""FixStand y marcha wait-mean sobre un único estado físico de MuJoCo por ensayo."""
import argparse
from contextlib import nullcontext
import csv
import json
import math
from pathlib import Path
import time

import mujoco
import numpy as np

from a2_policy import JOINT_NAMES, LEGS, PERIOD
from transicion_student import SCHEDULE, StandingSimulation, mean_neutral_target, read_capture, trial

HOLD_S = 3.
STIFFNESS_FACTOR = 4.


def archived_torque(path):
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    end = float(rows[-1]["pc_time_s"])
    values = np.array([json.loads(row["tau_est_sdk_nm"]) for row in rows
                       if float(row["pc_time_s"]) >= end-5], dtype=float)
    if values.ndim != 2 or values.shape[1] != 12 or not np.isfinite(values).all():
        raise ValueError("tau_est inválido")
    return {"samples": len(values), "median_nm": np.median(values, axis=0).tolist(),
            "p05_nm": np.percentile(values, 5, axis=0).tolist(),
            "p95_nm": np.percentile(values, 95, axis=0).tolist(),
            "scope": "comparison only; no archived torque enters the simulator control"}


def snapshot(sim):
    m, d = sim.model, sim.data
    forces = dict.fromkeys(LEGS, 0.)
    nonfoot_z = 0.
    for index, contact in enumerate(d.contact):
        a, b = int(contact.geom1), int(contact.geom2)
        if m.geom_bodyid[a] == sim.terrain and m.geom_bodyid[b] >= sim.base:
            robot, sign = b, 1.
        elif m.geom_bodyid[b] == sim.terrain and m.geom_bodyid[a] >= sim.base:
            robot, sign = a, -1.
        else:
            continue
        wrench = np.zeros(6)
        mujoco.mj_contactForce(m, d, index, wrench)
        vertical = float(sign * (contact.frame.reshape(3,3).T @ wrench[:3])[2])
        if robot in sim.feet:
            forces[sim.feet[robot]] += vertical
        else:
            nonfoot_z += vertical
    foot_clearance = {
        leg: float(d.geom_xpos[geom, 2]-m.geom_size[geom, 0]-d.geom_xpos[0, 2])
        for geom, leg in sim.feet.items()
    }
    return {"t_s": float(d.time), "base_xyz_m": d.qpos[:3].tolist(),
            "base_quat_wxyz": d.qpos[3:7].tolist(), "base_velocity_world_m_s":d.qvel[:3].tolist(),
            "tilt_deg":sim.tilt_deg(), "q_rad":d.qpos[sim.qids].tolist(), "dq_rad_s":d.qvel[sim.vids].tolist(),
            "target_rad":d.ctrl[sim.aids].tolist(),
            "q_error_vs_measured_deg":np.degrees(d.qpos[sim.qids]-sim.initial_q).tolist(),
            "target_minus_measured_sim_deg":np.degrees(d.ctrl[sim.aids]-d.qpos[sim.qids]).tolist(),
            "applied_actuator_force_nm":d.actuator_force[sim.aids].tolist(),
            "bias_generalized_joint_force_nm":d.qfrc_bias[sim.vids].tolist(),
            "constraint_generalized_joint_force_nm":d.qfrc_constraint[sim.vids].tolist(),
            "foot_vertical_force_n": forces, "nonfoot_vertical_force_n": nonfoot_z,
            "total_vertical_contact_force_n": float(sum(forces.values())+nonfoot_z),
            "foot_clearance_m":foot_clearance,"contacts":sim.contacts(),
            "kp_sim":m.actuator_gainprm[sim.aids,0].tolist(),
            "kd_sim":(-m.actuator_biasprm[sim.aids,2]).tolist()}


class HoldStiffness:
    """Scale only the simulated joint servo during FixStand and its handoff."""
    def __init__(self, sim, factor):
        self.sim = sim
        self.factor = factor
        m = sim.model
        self.gain = m.actuator_gainprm[sim.aids].copy()
        self.bias = m.actuator_biasprm[sim.aids].copy()

    def set(self, factor):
        m, ids = self.sim.model, self.sim.aids
        m.actuator_gainprm[ids, 0] = self.gain[:, 0]*factor
        m.actuator_biasprm[ids, 1] = self.bias[:, 1]*factor
        m.actuator_biasprm[ids, 2] = self.bias[:, 2]*math.sqrt(factor)

    def restore_during(self, elapsed, blend):
        self.set(1. + (self.factor-1.)*(1.-min(elapsed/blend, 1.)))

    def restored(self):
        m, ids = self.sim.model, self.sim.aids
        return bool(np.array_equal(m.actuator_gainprm[ids], self.gain)
                    and np.array_equal(m.actuator_biasprm[ids], self.bias))


def hold(sim, output, viewer):
    initial = snapshot(sim)
    origin = sim.data.qpos[:2].copy()
    illegal = set()
    peak_error = 0.
    samples = []
    fall = False
    trunk = False
    closed = False
    first_nonfoot = None
    with output.open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(initial)+["fall"])
        writer.writeheader()
        writer.writerow(initial | {"fall":False})
        for step in range(round(HOLD_S/PERIOD)):
            if viewer is not None and not viewer.is_running():
                closed = True
                break
            start = time.perf_counter()
            with viewer.lock() if viewer is not None else nullcontext():
                fell, body, contacts, _ = sim.physics(sim.initial_q)
                row = snapshot(sim)
            illegal.update(contacts)
            if contacts and first_nonfoot is None:
                first_nonfoot = row["t_s"]
            peak_error = max(peak_error, max(abs(a) for a in row["q_error_vs_measured_deg"]))
            trunk |= body
            fall |= fell
            samples.append(row)
            writer.writerow(row | {"fall":fell})
            if viewer is not None:
                viewer.sync()
                time.sleep(max(0., PERIOD-(time.perf_counter()-start)))
            if fell:
                break
    end = samples[-1] if samples else initial
    last = samples[-round(1./PERIOD):]
    all_four = bool(last) and all(len(row["contacts"]["feet"]) == 4 for row in last)
    speed = float(np.mean([np.linalg.norm(row["base_velocity_world_m_s"][:2]) for row in last])) if last else None
    joint_speed = float(np.mean([np.linalg.norm(row["dq_rad_s"]) for row in last])) if last else None
    complete = len(samples)==round(HOLD_S/PERIOD)
    passed = (complete and not fall and not illegal and all_four and peak_error<=5.
              and speed<=.03 and joint_speed<=.3)
    return {"status":"passed" if passed else "viewer_closed" if closed else "failed",
            "initial":initial,"final":end,"duration_s":len(samples)*PERIOD,
            "fall":fall,"trunk_contact":trunk,"nonfoot_contacts":sorted(illegal),
            "first_nonfoot_detected_s":first_nonfoot,"max_joint_deviation_deg":peak_error,
            "drift_m":float(np.linalg.norm(sim.data.qpos[:2]-origin)),
            "last_second_all_four_feet":all_four,
            "last_second_mean_planar_speed_m_s":speed,"last_second_mean_joint_speed_norm_rad_s":joint_speed,
            "criterion":"3 s; no fall/nonfoot; four feet throughout last second; max deviation <=5 deg; last-second average base/joint speeds <=0.03 m/s and 0.3 rad/s"}


def run_case(q, quat, out, case, neutral_target, blend, view, *, command_segments=None, reactivation_s=None):
    sim = StandingSimulation(q, quat)
    durations = ({label: len(commands) * PERIOD for label, commands in command_segments}
                 if command_segments is not None else {label: seconds for label, seconds, _ in SCHEDULE})
    factor = STIFFNESS_FACTOR if case=="stiffness" else 1.
    support = HoldStiffness(sim, factor)
    # Store the original zero-error, loaded geometry before changing any gains.
    geometry = sim.reconstruction
    before = snapshot(sim)
    mass = float(sum(sim.model.body_mass[sim.base:]))
    diagnostic = {"geometry":geometry,"initial_p0":before,"gravity_m_s2":sim.model.opt.gravity.tolist(),
                  "robot_mass_kg":mass,"expected_weight_n":mass*abs(float(sim.model.opt.gravity[2])),
                  "force_timing":"contacts and solver forces correspond to most recent physics evaluation (up to one 5 ms substep before the recorded q)",
                  "joint_order":JOINT_NAMES}
    support.set(factor)
    events = [{"t_s":float(sim.data.time),"phase":"FixStand","event":"start"}]
    context = nullcontext(None)
    if view:
        from mujoco.viewer import launch_passive
        context = launch_passive(sim.model, sim.data)
    with context as viewer:
        if viewer is not None:
            with viewer.lock():
                viewer.cam.type=mujoco.mjtCamera.mjCAMERA_TRACKING
                viewer.cam.trackbodyid=sim.base
                viewer.cam.distance=2.
        standing=hold(sim,out/f"{case}-hold.csv",viewer)
        events.append({"t_s":float(sim.data.time),"phase":"FixStand","event":standing["status"]})
        walking=None
        activation=None
        gain_restored_at=None
        if standing["status"]=="passed":
            # Same MjData, same simulation time, no reset or relocation.
            activation=snapshot(sim)
            events.append({"t_s":activation["t_s"],"phase":"GRU","event":"start"})
            def fade(elapsed):
                nonlocal gain_restored_at
                if gain_restored_at is not None:
                    return
                support.restore_during(elapsed, blend)
                if elapsed >= blend and support.restored():
                    gain_restored_at = float(sim.data.time)
            walking=trial(q,quat,out/f"{case}-walk.csv","wait-mean",blend,False,
                          simulation=sim,neutral_target=neutral_target,viewer_context=nullcontext(viewer),
                          before_physics=fade,command_segments=command_segments,reactivation_s=reactivation_s)
            if gain_restored_at is not None:
                events.append({"t_s":gain_restored_at,"phase":"gain_handoff","event":"original_P0_restored"})
            for event in walking["transitions"]:
                events.append({"t_s":event["t_s"],"phase":event["to"],"event":event["reason"]})
            for maneuver in walking["maneuvers"]:
                observed=maneuver["direction_observed"]
                ok=maneuver["zero_settled"] if observed is None else observed
                ok=bool(ok and not maneuver["nonfoot_contacts"] and math.isclose(maneuver["duration_s"],durations[maneuver["maneuver"]],abs_tol=1e-8))
                events.append({"t_s":maneuver["start_s"],"phase":maneuver["maneuver"],"event":"start"})
                events.append({"t_s":maneuver["end_s"],"phase":maneuver["maneuver"],"event":"passed" if ok else "failed"})
            events.append({"t_s":float(sim.data.time),"phase":"GRU","event":walking["status"]})
    continuous_boundary = bool(walking and
          math.isclose(walking["activation_time_s"], standing["final"]["t_s"], abs_tol=1e-8) and
          np.array_equal(walking["first_activation"]["q_before_rad"], standing["final"]["q_rad"]) and
          np.array_equal(walking["first_activation"]["applied_target_rad"], standing["final"]["target_rad"]))
    passed=bool(walking and continuous_boundary and gain_restored_at is not None and support.restored() and walking["completed_without_nonfoot_contact"]
                and walking["all_requested_directions_observed"] and walking["all_zero_segments_settled"] and math.isclose(sim.data.time,HOLD_S+sum(durations.values()),abs_tol=1e-8))
    return {"case":case,"support_stiffness_factor_sim_only":factor,
            "diagnosis":diagnostic,"fixstand":standing,"activation_before":activation,
            "walking":walking,"events":sorted(events,key=lambda event:event["t_s"]),
            "final":snapshot(sim),"physics_time_s":float(sim.data.time),
            "original_p0_restored_at_end":support.restored(),
            "original_p0_restored_at_s":gain_restored_at,"continuous_boundary_verified":continuous_boundary,
            "continuous_pass":passed,"physics_resets_after_initialization":0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--case",choices=["all","p0","stiffness"],default="all")
    parser.add_argument("--blend-s",type=float,default=.5)
    parser.add_argument("--view",action="store_true")
    args=parser.parse_args()
    if not math.isfinite(args.blend_s) or not PERIOD<=args.blend_s<=5.:
        parser.error("--blend-s debe estar entre 0.02 y 5 segundos")
    q, quat, capture=read_capture(args.csv)
    args.out.mkdir(parents=True,exist_ok=False)
    result={"scope":"simulation_only","capture":capture,"physical_tau_est":archived_torque(args.csv),
            "neutral_target_source":"separate prior 4 s simulation calibration; no reset in evaluated chain",
            "cases":{}}
    cases=("p0","stiffness") if args.case=="all" else (args.case,)
    # Independent wait-mean calibration, as in the published reference.
    neutral_target=mean_neutral_target(q,quat,args.blend_s)
    for case in cases:
        record=run_case(q,quat,args.out,case,neutral_target,args.blend_s,args.view)
        result["cases"][case]=record
        (args.out/f"{case}.json").write_text(json.dumps(record,indent=2)+"\n")
        print(json.dumps({"case":case,"fixstand":record["fixstand"]["status"],
                          "continuous_pass":record["continuous_pass"],"physics_time_s":record["physics_time_s"]}),flush=True)
    (args.out/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
    print("Resumen:",args.out/"summary.json")


if __name__=="__main__":
    main()
