"""Send keyboard requests through SSH to shadow mode on the Go2."""

import argparse
import os
import re
import subprocess
import time

from teleop_input import KeyboardWindow, STOP


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="usuario@host; por ejemplo unitree@192.168.123.18")
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.-]*", args.host) is None:
        parser.error("Usa usuario@host o usuario@IPv4")
    if not 1 <= args.seconds <= 60:
        parser.error("--seconds debe estar entre 1 y 60")
    remote = (
        'cd "$HOME/go2-shadow" && mkdir -p pruebas && '
        'env -u PYTHONPATH -u CYCLONEDDS_URI '
        'CYCLONEDDS_HOME="$PWD/deps/cyclonedds/install" '
        'LD_LIBRARY_PATH="$PWD/deps/cyclonedds/install/lib" '
        '.venv-a2/bin/python a2_robot.py shadow --commands-stdin --iface eth10 --policy-update student '
        f'--seconds {args.seconds} --csv "pruebas/student-teclas-$(date +%Y%m%d-%H%M%S).csv"'
    )
    print("Abriendo el mando en modo sombra. Completa la autenticación SSH en esta terminal.", flush=True)
    with subprocess.Popen(["ssh", "-T", "-o", "ConnectTimeout=5", args.host, remote],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        fd = process.stdin.fileno()
        os.set_blocking(fd, False)
        keyboard = None
        try:
            for line in process.stdout:
                if line.strip() == b"SHADOW_INPUT_READY":
                    break
                print(line.decode(errors="replace").rstrip(), flush=True)
            else:
                return process.wait()
            keyboard = KeyboardWindow("Go2 · mando en sombra por SSH")
            while process.poll() is None and keyboard.running:
                command = keyboard.poll()
                try:
                    os.write(fd, f"{command}\n".encode("ascii"))
                except BlockingIOError:
                    pass
                except BrokenPipeError:
                    break
                time.sleep(.05)
        finally:
            try:
                os.write(fd, f"{STOP}\n".encode("ascii"))
            except (BlockingIOError, BrokenPipeError):
                pass
            process.stdin.close()
            if keyboard is not None:
                keyboard.destroy()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for line in process.stdout:
            print(line.decode(errors="replace").rstrip(), flush=True)
        return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
