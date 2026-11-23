"""Comprueba el perfil y una postura Go2 con telemetría de solo lectura."""

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from a2_policy import JOINT_NAMES, gravity_body, policy_spec
from a2_robot import MAX_STATE_AGE, load_profile

ROOT = Path(__file__).resolve().parent
VECTOR_FIELDS = {
    "sign": (12,), "sdk_zero_rad": (12,), "joint_limits_rad": (12, 2),
    "kp": (12,), "kd": (12,), "stop_kd": (12,), "max_start_error_rad": (12,),
    "max_target_error_rad": (12,), "max_estimated_torque_nm": (12,),
}


def read_rows(path):
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    if len({row["dds_tick"] for row in rows}) < 2:
        raise ValueError("Se necesitan al menos dos ticks DDS distintos")
    return rows


def read_vector(rows, field, size):
    values = np.array([json.loads(row[field]) for row in rows], dtype=float)
    if values.shape != (len(rows), size) or not np.isfinite(values).all():
        raise ValueError(f"Lecturas inválidas en {field}")
    return values


def pending_fields(profile, iface):
    pending = []
    if profile.get("iface") != iface:
        pending.append(f'iface debe ser "{iface}"')
    if profile.get("joint_names") != JOINT_NAMES:
        pending.append("joint_names debe coincidir con la plantilla del alumno")
    if not isinstance(profile.get("robot_firmware"), str) or not profile["robot_firmware"].strip():
        pending.append("robot_firmware: falta la versión que muestra la app")
    if profile.get("frames_verified") is not True:
        pending.append("frames_verified: falta comprobar marcos, signos, ceros e IMU")
    for name, shape in VECTOR_FIELDS.items():
        try:
            values = np.asarray(profile.get(name), dtype=float)
            if values.shape != shape or not np.isfinite(values).all():
                pending.append(f"{name}: faltan valores válidos")
        except (TypeError, ValueError):
            pending.append(f"{name}: faltan valores válidos")
    return pending


def review(csv_path, profile_path, iface):
    rows = read_rows(csv_path)
    sdk_q = read_vector(rows, "q_sdk_in_actor_order_rad", 12)
    dq = read_vector(rows, "dq_sdk_in_actor_order_rad_s", 12)
    imu = read_vector(rows, "imu_wxyz", 4)
    estimated_torque = read_vector(rows, "tau_est_sdk_nm", 12)
    age = np.array([float(r["age_ms"]) for r in rows])
    if not np.isfinite(age).all() or np.any(age < 0):
        raise ValueError("Edad de telemetría inválida")
    if np.any(np.abs(np.linalg.norm(imu, axis=1) - 1.) > .02):
        raise ValueError("Cuaternión IMU fuera de rango")
    q0 = np.array(policy_spec("student")["q0"])
    print(f"CSV: {csv_path}")
    print(f"{len(rows)} muestras, edad máxima registrada {max(age):.1f} ms")
    problems = []
    if max(age) > MAX_STATE_AGE * 1000:
        problems.append("alguna muestra superó 40 ms al registrarse")
    if np.max(np.abs(dq)) > .3:
        problems.append("la velocidad articular superó 0,30 rad/s en la captura")
    if max(gravity_body(quat)[2] for quat in imu) > -.95:
        problems.append("la inclinación medida supera el límite de arranque")
    if not profile_path.is_file():
        problems.append(f"falta el perfil {profile_path}")
        calibrated = None
    else:
        profile = json.loads(profile_path.read_text())
        if not isinstance(profile, dict):
            raise ValueError("El perfil debe ser un objeto JSON")
        fields = pending_fields(profile, iface)
        problems += fields
        calibrated = load_profile(profile_path, iface) if not fields else None
    if calibrated is None:
        print("Articulación                  SDK mediana [rad]  Nominal modelo [rad]")
        for name, angle, nominal in zip(JOINT_NAMES, np.median(sdk_q, axis=0), q0):
            print(f"{name:30s} {angle:17.3f} {nominal:21.3f}")
    else:
        sign, zero, limits, _, _, _, start, _, torque = calibrated
        q = sign * (sdk_q - zero)
        error = np.max(np.abs(q - q0), axis=0)
        print("Articulación                  Error máximo [rad]  Límite [rad]")
        for i, name in enumerate(JOINT_NAMES):
            print(f"{name:30s} {error[i]:18.3f} {start[i]:13.3f}")
            if not limits[i, 0] <= q0[i] <= limits[i, 1]:
                problems.append(f"{name}: la pose nominal queda fuera de los límites")
            if q[:, i].min() < limits[i, 0] or q[:, i].max() > limits[i, 1]:
                problems.append(f"{name}: posición registrada fuera de los límites")
            if error[i] > start[i]:
                problems.append(f"{name}: fuera de tolerancia de la pose inicial")
            if np.max(np.abs(estimated_torque[:, i])) > torque[i]:
                problems.append(f"{name}: torque estimado fuera del límite durante la captura")
    if problems:
        print("REVISAR")
        for problem in problems:
            print(f"- {problem}")
        return 2
    print("OK: el perfil y la captura pasan la revisión de solo lectura")
    print("El ensayo requiere verificaciones físicas de soporte, paro y pérdida de comandos.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iface", default="eth10")
    parser.add_argument("--profile", type=Path, default=ROOT / "pruebas/a2-bench-profile.json")
    parser.add_argument("--csv", type=Path, help="Analizar una captura guardada")
    args = parser.parse_args()
    try:
        path = args.csv
        if path is None:
            output = ROOT / "pruebas"
            output.mkdir(exist_ok=True)
            path = Path(tempfile.mkdtemp(prefix="preflight-banco-", dir=output)) / "estado.csv"
            subprocess.run(
                [sys.executable, str(ROOT / "a2_robot.py"), "observe",
                 "--iface", args.iface, "--seconds", "3", "--csv", str(path)],
                check=True,
            )
        return review(path, args.profile, args.iface)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"REVISAR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
