"""Record Go2 telemetry or make one short, explicitly armed Sport test."""
import argparse
import csv
import math
import signal
import socket
from threading import Lock
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iface', required=True)
    parser.add_argument('--csv', required=True)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--pulse', choices=('forward', 'reverse', 'left', 'right', 'yaw'))
    parser.add_argument('--arm', action='store_true')
    args = parser.parse_args()
    if args.iface == 'lo' or args.iface not in dict(socket.if_nameindex()).values():
        parser.error('Selecciona la interfaz Ethernet del Go2')
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= (1 if args.pulse else 60):
        parser.error('Pulso máximo de 1 s o captura máxima de 60 s')
    if bool(args.pulse) != args.arm:
        parser.error('El ensayo de movimiento requiere --pulse y --arm juntos')

    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_

    def terminate(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    latest = None
    lock = Lock()

    def receive(msg):
        nonlocal latest
        with lock:
            latest = msg, time.monotonic()

    ChannelFactoryInitialize(0, args.iface)
    subscriber = ChannelSubscriber('rt/sportmodestate', SportModeState_)
    subscriber.Init(receive, 10)
    client = None
    moves = {'forward': (.15, 0., 0.), 'reverse': (-.10, 0., 0.),
             'left': (0., .10, 0.), 'right': (0., -.10, 0.), 'yaw': (0., 0., .20)}
    cmd = moves.get(args.pulse, (0., 0., 0.))
    movement_requested = False
    try:
        with open(args.csv, 'x', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['t_s', 'phase', 'sample_age_ms', 'cmd_vx_body_m_s', 'cmd_vy_body_m_s',
                             'cmd_yaw_rad_s', 'reported_vx_m_s', 'reported_vy_m_s', 'reported_vz_m_s',
                             'reported_yaw_rad_s', 'x_m', 'y_m', 'z_m', 'height_m', 'roll_rad',
                             'pitch_rad', 'mode', 'gait', 'error_code', 'rpc_ms', 'rpc_code'])
            wait_until = time.monotonic() + 4
            while latest is None and time.monotonic() < wait_until:
                time.sleep(.02)
            if latest is None:
                raise RuntimeError('Sin datos DDS rt/sportmodestate')
            if args.pulse:
                from unitree_sdk2py.go2.sport.sport_client import SportClient
                client = SportClient()
                client.SetTimeout(.25)
                client.Init()
            started = time.monotonic()
            while time.monotonic() < started + args.seconds:
                tick = time.monotonic()
                with lock:
                    msg, received = latest
                age = tick - received
                if age > .25 or msg.error_code:
                    raise RuntimeError(f'Telemetría caducada o error del robot: {age:.3f}s, código {msg.error_code}')
                roll, pitch, _ = msg.imu_state.rpy
                rpc_ms = rpc_code = ''
                if client is not None:
                    if not all(math.isfinite(v) and abs(v) <= .25 for v in (roll, pitch)):
                        raise RuntimeError('Inclinación fuera del margen del ensayo en plano')
                    movement_requested = True
                    rpc_code = client.Move(*cmd)
                    rpc_ms = (time.monotonic()-tick)*1000
                writer.writerow([tick-started, 'move' if client else 'observe', age*1000, *cmd, *msg.velocity, msg.yaw_speed,
                                 *msg.position, msg.body_height, roll, pitch, msg.mode, msg.gait_type,
                                 msg.error_code, rpc_ms, rpc_code])
                file.flush()
                if rpc_code not in ('', 0):
                    raise RuntimeError(f'Sport Move devolvió {rpc_code}')
                time.sleep(max(0., .10-(time.monotonic()-tick)))
            if movement_requested:
                code = client.StopMove()
                print(f'StopMove: {code}', flush=True)
                if code != 0:
                    raise RuntimeError('No se confirmó StopMove. Usa el mando físico.')
                movement_requested = False
                until = time.monotonic() + 2.
                while (tick := time.monotonic()) < until:
                    with lock:
                        msg, received = latest
                    roll, pitch, _ = msg.imu_state.rpy
                    writer.writerow([tick-started, 'after_stop', (tick-received)*1000,
                                     0., 0., 0., *msg.velocity, msg.yaw_speed, *msg.position,
                                     msg.body_height, roll, pitch, msg.mode, msg.gait_type,
                                     msg.error_code, '', ''])
                    time.sleep(.10)
    finally:
        if movement_requested:
            code = client.StopMove()
            print(f'StopMove: {code}', flush=True)
            if code != 0:
                raise RuntimeError('No se confirmó StopMove. Usa el mando físico.')


if __name__ == '__main__':
    main()
