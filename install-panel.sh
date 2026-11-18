#!/usr/bin/env bash
# Install the CPU panel and the pinned Unitree SDK on Ubuntu.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
sudo apt update
sudo apt install -y git python3-venv python3-dev python3-tk build-essential cmake libgl1 libglib2.0-0 libglfw3 iproute2 xdg-utils

sdk_rev=814556d15970dd2ecf1c9984e845ca02ab07e206
dds_rev=9995905bce6c4cf9f740d6438bbf7fcfd1c83dfd
mkdir -p deps pruebas
if [[ ! -d deps/sdk/.git ]]; then
  git clone https://github.com/unitreerobotics/unitree_sdk2_python.git deps/sdk
  git -C deps/sdk checkout --detach "$sdk_rev"
fi
if [[ ! -d deps/cyclonedds-panel/.git ]]; then
  git clone --branch 0.10.2 https://github.com/eclipse-cyclonedds/cyclonedds.git deps/cyclonedds-panel
fi
for spec in "deps/sdk:$sdk_rev" "deps/cyclonedds-panel:$dds_rev"; do
  path=${spec%%:*}
  revision=${spec##*:}
  if [[ "$(git -C "$path" rev-parse HEAD)" != "$revision" || -n "$(git -C "$path" status --porcelain --untracked-files=no)" ]]; then
    printf 'Revisa la revisión o cambios locales de %s antes de instalar.\n' "$path" >&2
    exit 1
  fi
done
dds="$PWD/deps/cyclonedds-panel"
cmake -S "$dds" -B "$dds/build" -DCMAKE_INSTALL_PREFIX="$dds/install" -DBUILD_TESTING=OFF
cmake --build "$dds/build" --parallel 2
cmake --install "$dds/build"

python3 -m venv .venv-a2
python=.venv-a2/bin/python
"$python" -m pip install 'torch==2.10.0' --index-url https://download.pytorch.org/whl/cpu
"$python" -m pip install -r requirements-sim.txt 'opencv-python==4.11.0.86'
CYCLONEDDS_HOME="$dds/install" "$python" -m pip install -e deps/sdk
"$python" -c 'import tkinter, torch, mujoco; from unitree_sdk2py.utils.crc import CRC; CRC(); print("Panel y SDK listos")'
printf 'Abre el panel con: bash abrir-panel.sh\n'
