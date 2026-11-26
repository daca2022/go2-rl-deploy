"""Replay recorded wireless-shadow commands on the continuous MuJoCo experiment."""
import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

from a2_policy import PERIOD
from transicion_continua import run_case
from transicion_student import read_capture, mean_neutral_target

AXES = ("cmd_vx", "cmd_vy", "cmd_yaw")
BLEND = .5


def timeline(path):
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    times = np.asarray([float(row["pc_time_s"]) for row in rows])
    values = np.asarray([[float(row[key]) for key in AXES] for row in rows])
    if (len(times)<2 or not np.isfinite(times).all()
            or not np.isfinite(values).all() or np.any(np.diff(times)<=0)):
        raise ValueError("Se requieren consignas finitas y tiempos estrictamente crecientes")
    relative = times-times[0]
    ticks = np.arange(math.ceil(relative[-1]/PERIOD))*PERIOD
    indices = np.searchsorted(relative,ticks,side="right")-1
    directions = np.sign(values).astype(int)
    raw_segments = []
    group_ids = np.empty(len(rows),dtype=int)
    pulse_count = center_count = 0
    for sign, group in itertools.groupby(range(len(rows)), key=lambda i:tuple(directions[i])):
        members = list(group)
        first, last = members[0], members[-1]
        if any(sign):
            pulse_count += 1
            label = f"pulso_{pulse_count:02d}"
        else:
            center_count += 1
            label = f"centro_{center_count:02d}"
        group_ids[first:last+1] = len(raw_segments)
        raw_segments.append({"label":label,"sign":[int(value) for value in sign],"source_start_s":float(relative[first]),
                             "source_end_s":float(relative[last+1] if last+1<len(rows) else relative[last]),
                             "source_rows":len(members)})
    commands = [tuple(row) for row in values[indices].tolist()]
    segments = []
    sampled_labels = []
    for group, members in itertools.groupby(range(len(ticks)),key=lambda i:group_ids[indices[i]]):
        members = list(members)
        label = raw_segments[group]["label"]
        segment = raw_segments[group]
        segment["sim_start_s"] = float(ticks[members[0]])
        segment["sim_end_s"] = float(ticks[members[-1]]+PERIOD)
        segment["sim_cycles"] = len(members)
        segments.append((label,[commands[i] for i in members]))
        sampled_labels.extend([label]*len(members))
    return {"times":times,"ticks":ticks,"indices":indices,"commands":commands,
            "segments":segments,"raw_segments":raw_segments,"labels":sampled_labels,
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def trace_window(rows, prior):
    points = np.array([[float(prior["x_m"]),float(prior["y_m"])]]+
                      [[float(row["x_m"]),float(row["y_m"])] for row in rows])
    yaws = np.unwrap([float(prior["yaw_rad"])]+[float(row["yaw_rad"]) for row in rows])
    return {"net_planar_m":float(np.linalg.norm(points[-1]-points[0])),
            "path_length_m":float(np.linalg.norm(np.diff(points,axis=0),axis=1).sum()),
            "yaw_delta_deg":float(np.degrees(yaws[-1]-yaws[0])),
            "accumulated_abs_yaw_deg":float(np.degrees(np.abs(np.diff(yaws)).sum()))}


def center_details(rows, prior, phase):
    details = trace_window(rows,prior)
    stable_at = None
    window = round(1/PERIOD)
    for i in range(window-1,len(rows)):
        batch = rows[i-window+1:i+1]
        if not all(row["controller"]=="wait" and float(row["blend_weight"])>=1.
                   and not row["nonfoot"] and row["fall"]=="0" for row in batch):
            continue
        speed = np.mean([math.hypot(float(r["vx_body_m_s"]),float(r["vy_body_m_s"])) for r in batch])
        yaw_speed = np.mean([abs(float(r["yaw_rate_rad_s"])) for r in batch])
        joint_speed = np.mean([float(r["joint_speed_norm_rad_s"]) for r in batch])
        if speed<=.03 and yaw_speed<=.05 and joint_speed<=.3:
            stable_at = i
            break
    details["published_end_monitor_pass"] = phase["zero_settled"]
    details["fixed_wait_stable_for_1s_before_next_pulse"] = stable_at is not None
    details["seconds_to_confirm_stable_wait"] = (float(rows[stable_at]["t_s"])-float(prior["t_s"])
                                                 if stable_at is not None else None)
    details["movement_until_stable_wait_confirmed"] = (trace_window(rows[:stable_at+1],prior)
                                                       if stable_at is not None else None)
    details["final_1s_planar_speed_m_s"] = phase["final_1s_mean_planar_speed_m_s"]
    details["final_1s_joint_speed_norm_rad_s"] = phase["final_1s_mean_joint_speed_norm_rad_s"]
    return details


def pulse_reports(record, timeline_data, rows):
    phases = {phase["maneuver"]:phase for phase in record["walking"]["maneuvers"]}
    grouped = {}
    cursor = 0
    for name, group in itertools.groupby(rows,key=lambda row:row["maneuver"]):
        current = list(group)
        grouped[name] = (cursor, current)
        cursor += len(current)
    reports = []
    raw_segments = timeline_data["raw_segments"]
    for i,segment in enumerate(raw_segments):
        if not any(segment["sign"]):
            continue
        report = dict(segment)
        name = segment["label"]
        if name not in phases:
            report["status"] = "not_sampled_or_not_reached"
            reports.append(report)
            continue
        phase = phases[name]
        displacement = phase["local_displacement_m"]
        rotation = phase["yaw_delta_deg"]
        actual = [*displacement, math.radians(rotation)]
        requested = {axis:{"signed_response":actual[j]*sign,
                           "in_requested_direction":bool(actual[j]*sign>0.),
                           "published_threshold_pass":bool(actual[j]*sign>(.05 if j==2 else .02))}
                     for j,(axis,sign) in enumerate(zip(AXES,segment["sign"])) if sign}
        report.update({"status":"measured","duration_sim_s":phase["duration_s"],
                       "local_displacement_m":displacement,"yaw_delta_deg":rotation,
                       "requested_axes":requested,
                       "mean_body_velocity":phase["mean_body_velocity"]})
        _, pulse = grouped[name]
        pulse_commands = np.array([[float(row[key]) for key in AXES] for row in pulse])
        report["mean_recorded_command_at_50hz"] = dict(zip(AXES,np.mean(pulse_commands,axis=0).tolist()))
        report["peak_abs_recorded_command_at_50hz"] = dict(zip(AXES,np.max(np.abs(pulse_commands),axis=0).tolist()))
        report["last_applied_blend_weight"] = float(pulse[-1]["blend_weight"])
        following = raw_segments[i+1] if i+1<len(raw_segments) else None
        if following and not any(following["sign"]) and following["label"] in grouped:
            offset, center = grouped[following["label"]]
            report["after_release"] = center_details(center,rows[offset-1],phases[following["label"]])
            report["after_release"]["duration_s"] = phases[following["label"]]["duration_s"]
        else:
            report["after_release"] = None
        reports.append(report)
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration",type=Path,required=True,help="Primera captura de pie")
    parser.add_argument("--initial",type=Path,required=True,help="Segunda captura de pie")
    parser.add_argument("--remote-csv",type=Path,required=True,help="Registro del mando en shadow")
    parser.add_argument("--out",type=Path,required=True,help="Directorio nuevo")
    parser.add_argument("--view",action="store_true")
    args = parser.parse_args()
    q1, imu1, capture1 = read_capture(args.calibration)
    target = mean_neutral_target(q1, imu1, BLEND)
    q2, imu2, capture2 = read_capture(args.initial)
    data = timeline(args.remote_csv)
    args.out.mkdir(parents=True,exist_ok=False)
    with (args.out/"consignas_50hz.csv").open("x",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["decision_time_s","source_pc_time_s","source_row_zero_based","segment",*AXES])
        for tick, index, label, command in zip(data["ticks"],data["indices"],data["labels"],data["commands"]):
            writer.writerow([tick,data["times"][index],index,label,*command])
    record = run_case(q2,imu2,args.out,"stiffness",target,BLEND,args.view,command_segments=data["segments"])
    walking = record["walking"]
    matches = None
    reports = []
    if walking:
        with (args.out/"stiffness-walk.csv").open(newline="") as file:
            rows = list(csv.DictReader(file))
        commands = [tuple(float(row[key]) for key in AXES) for row in rows]
        matches = commands==data["commands"][:len(rows)]
        reports = pulse_reports(record,data,rows)
    summary = {"scope":"simulation_only_recorded_remote",
               "calibration_capture_sha256":capture1["csv_sha256"],
               "initial_capture_sha256":capture2["csv_sha256"],
               "remote_csv_sha256":data["sha256"],
               "remote_rows":len(data["times"]),
               "recorded_duration_s":float(data["times"][-1]-data["times"][0]),
               "replay_cycles_planned":len(data["ticks"]),
               "replay_duration_s":len(data["ticks"])*PERIOD,
               "resampling":"last available row at each 20 ms decision; no interpolation or extension of pulses",
               "raw_segments":data["raw_segments"],
               "all_applied_commands_match_resampling":matches,
               "all_source_pulses_preserved_at_50hz":all("sim_cycles" in segment for segment in data["raw_segments"] if any(segment["sign"])),
               "full_replay_completed":bool(walking and walking["samples"] == len(data["ticks"]) and walking["status"] == "complete"),
               "frozen_wait_target_rad":target.tolist(),
               "continuous_case":record,"pulses":reports}
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print("FixStand:",record["fixstand"]["status"])
    print("Tiempo simulado:",record["physics_time_s"])
    print("Pulsos medidos:",len([p for p in reports if p["status"]=="measured"]))
    print("Resumen:",args.out/"summary.json")


if __name__=="__main__":
    main()
