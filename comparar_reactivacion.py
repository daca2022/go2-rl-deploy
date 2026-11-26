"""Compare only the simulated wait-to-GRU blend time, with a centered control."""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from a2_policy import PERIOD
from reproducir_mando import (AXES, BLEND, center_details,
                               run_recording, timeline, trace_window)
from transicion_continua import run_case
from transicion_student import mean_neutral_target, read_capture, ZERO

DURATIONS = (.5, .2, .1)


def read_trace(path):
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def activation_prior(record):
    state = record["activation_before"]
    w,x,y,z = state["base_quat_wxyz"]
    heading = math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
    return {"x_m":state["base_xyz_m"][0],"y_m":state["base_xyz_m"][1],
            "yaw_rad":heading,"t_s":state["t_s"]}


def centered_window(rows, prior):
    result = trace_window(rows, prior)
    heading = float(prior["yaw_rad"])
    dx = float(rows[-1]["x_m"])-float(prior["x_m"])
    dy = float(rows[-1]["y_m"])-float(prior["y_m"])
    result["local_displacement_m"] = [math.cos(heading)*dx+math.sin(heading)*dy,
                                       -math.sin(heading)*dx+math.cos(heading)*dy]
    return result


def reference_drift(data, q, quat, target, out):
    out.mkdir()
    segments = [("centro_sin_pulsos",[ZERO]*len(data["ticks"]))]
    record = run_case(q,quat,out,"stiffness",target,BLEND,False,command_segments=segments)
    if not record["walking"] or record["walking"]["samples"] != len(data["ticks"]):
        raise RuntimeError("La corrida centrada no completó el horizonte")
    rows = read_trace(out/"stiffness-walk.csv")
    prior = activation_prior(record)
    total = center_details(rows,prior,record["walking"]["maneuvers"][0])
    windows = {}
    for segment in data["raw_segments"]:
        if not any(segment["sign"]) or "sim_cycles" not in segment:
            continue
        start = round(segment["sim_start_s"]/PERIOD)
        end = start + segment["sim_cycles"]
        window = centered_window(rows[start:end],rows[start-1] if start else prior)
        windows[segment["label"]] = window
    result = {"scope":"centered_control_simulation","record":record,"total":total,
              "matched_pulse_windows":windows}
    (out/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
    return result


def evaluate(summary, drift):
    pulses = summary["pulses"]
    measured = [p for p in pulses if p["status"]=="measured"]
    scores = []
    reversed_correct = False
    thresholds = directions = 0
    for pulse in measured:
        window = drift["matched_pulse_windows"][pulse["label"]]
        pulse["matched_centered_motion"] = window
        response = [*window["local_displacement_m"],math.radians(window["yaw_delta_deg"])]
        for index,(axis,sign) in enumerate(zip(AXES,pulse["sign"])):
            if not sign:
                continue
            requested = pulse["requested_axes"][axis]
            integral = abs(pulse["integral_requested_at_50hz"][axis])
            requested["centered_control_signed_response"] = response[index]
            requested["difference_vs_centered_control"] = requested["actual_signed"]-response[index]
            scores.append(requested["signed_response"]/integral)
            thresholds += int(requested["published_threshold_pass"])
            directions += int(requested["in_requested_direction"])
            if axis=="cmd_vx" and sign<0:
                reversed_correct = requested["in_requested_direction"]
    record = summary["continuous_case"]
    walk = record["walking"]
    if not walk:
        raise RuntimeError("No se completó FixStand")
    stable = sum(p["after_release"]["fixed_wait_stable_for_1s_before_next_pulse"]
                 for p in measured if p["after_release"])
    eligible = (summary["full_replay_completed"] and walk["completed_without_nonfoot_contact"]
                and walk["max_tilt_deg"]<=15.)
    return {"reactivation_s":summary["reactivation_s"],"eligible":eligible,
            "direction_count":directions,"threshold_count":thresholds,
            "reverse_correct":reversed_correct,"mean_signed_fraction_of_requested_integral":float(np.mean(scores)) if scores else 0.,
            "stable_wait_count":stable,"max_target_step_deg":walk["max_target_step_deg"],
            "max_tilt_deg":walk["max_tilt_deg"],"duration_s":record["physics_time_s"],
            "fall":walk["status"]=="fall","nonfoot_contacts":walk["nonfoot_contacts"],
            "trunk_contact":walk["trunk_contact"]}



def write_comparison_tables(out, variants, metrics):
    with (out/"comparacion-variantes.csv").open("x",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    rows=[]
    for key,summary in variants.items():
        for p in summary["pulses"]:
            if p["status"]!="measured":
                continue
            release=p["after_release"]
            for axis,response in p["requested_axes"].items():
                rows.append({"reactivation_s":key,"pulse":p["label"],"axis":axis,
                    "source_integral_m_or_rad":p["integral_requested_source"][axis],
                    "replay_integral_m_or_rad":p["integral_requested_at_50hz"][axis],
                    "actual_signed_m_or_rad":response["actual_signed"],
                    "centered_signed_m_or_rad":response["centered_control_signed_response"],
                    "direction_correct":response["in_requested_direction"],
                    "threshold_pass":response["published_threshold_pass"],
                    "pulse_max_target_step_deg":p["max_target_step_deg"],
                    "pulse_max_tilt_deg":p["max_tilt_deg"],
                    "pulse_nonfoot_contacts":"|".join(p["nonfoot_contacts"]),
                    "pulse_instability_observed":p["instability_observed"],
                    "release_duration_s":release["duration_s"] if release else None,
                    "release_net_planar_m":release["net_planar_m"] if release else None,
                    "release_path_length_m":release["path_length_m"] if release else None,
                    "release_yaw_delta_deg":release["yaw_delta_deg"] if release else None,
                    "release_max_target_step_deg":release["max_target_step_deg"] if release else None,
                    "release_max_tilt_deg":release["max_tilt_deg"] if release else None,
                    "release_nonfoot_contacts":"|".join(release["nonfoot_contacts"]) if release else None,
                    "release_wait_result":release["wait_result"] if release else None,
                    "release_instability_observed":release["instability_observed"] if release else None})
    if rows:
        with (out/"comparacion-pulsos.csv").open("x",newline="") as file:
            writer=csv.DictWriter(file,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration",type=Path,required=True)
    parser.add_argument("--initial",type=Path,required=True)
    parser.add_argument("--remote-csv",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args = parser.parse_args()
    q1, imu1, c1 = read_capture(args.calibration)
    q2, imu2, c2 = read_capture(args.initial)
    target = mean_neutral_target(q1,imu1,BLEND)
    data = timeline(args.remote_csv)
    args.out.mkdir(parents=True,exist_ok=False)
    drift = reference_drift(data,q2,imu2,target,args.out/"centered")
    results = {}
    metrics = []
    for duration in DURATIONS:
        key = f"{duration:.2f}"
        directory = args.out/f"reactivation-{key}"
        summary=run_recording(q2,imu2,c1,c2,target,data,directory,reactivation_s=duration)
        score=evaluate(summary,drift)
        summary["comparison_metrics"]=score
        results[key]=summary
        metrics.append(score)
        print(json.dumps(score),flush=True)
    base_jump = metrics[0]["max_target_step_deg"]
    for score in metrics:
        score["max_jump_change_percent_vs_reference"]=100*(score["max_target_step_deg"]/base_jump-1)
    for key, summary in results.items():
        (args.out/f"reactivation-{key}"/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    write_comparison_tables(args.out,results,metrics)
    # Select a candidate from complete, noncontact runs: threshold count, retroceso,
    # correct direction count, normalised response and then smaller target increments.
    eligible = [score for score in metrics if score["eligible"]]
    best = max(eligible,key=lambda score:(score["threshold_count"],score["reverse_correct"],
                                           score["direction_count"],score["mean_signed_fraction_of_requested_integral"],
                                           -score["max_target_step_deg"])) if eligible else None
    protocol = None
    if best is not None:
        out = args.out/"protocol-3s"
        out.mkdir()
        protocol = run_case(q2,imu2,out,"stiffness",target,BLEND,False,
                            reactivation_s=best["reactivation_s"])
        (out/"summary.json").write_text(json.dumps(protocol,indent=2)+"\n")
    summary = {"scope":"simulation_only_reactivation_development","initial_blend_s":BLEND,
               "return_to_wait_blend_s":BLEND,"frozen_wait_target_rad":target.tolist(),
               "capture_hashes":{"calibration":c1["csv_sha256"],"initial":c2["csv_sha256"],"remote":data["sha256"]},
               "centered_control":drift,"variants":results,"comparison":metrics,
               "selection_rule":"complete without nonfoot contacts or >15 deg tilt; threshold count, reverse sign, correct direction count, signed response fraction, smaller max target step",
               "selected_reactivation_s":best["reactivation_s"] if best else None,"protocol_3s":protocol}
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print("Seleccionada:",summary["selected_reactivation_s"],"Protocolo 3s:",protocol["continuous_pass"] if protocol else None)
    print("Resumen:",args.out/"summary.json")


if __name__=="__main__":
    main()
