# Mando del alumno GRU

La política recibe una velocidad de avance, lateral y giro en el marco del cuerpo. Produce 12 objetivos articulares a 50 Hz. Para recorrer una distancia, el programa de MuJoCo mide cuánto se desplazó el cuerpo y ajusta la consigna hasta que se estabiliza cerca del destino.

## MuJoCo en la PC

Clona el repositorio si todavía no tienes una copia. Ejecuta `bash install-panel.sh` una vez para crear `.venv-a2` en Ubuntu 22.04.

```bash
cd ~/go2-rl-deploy
git pull --ff-only
mkdir -p pruebas
.venv-a2/bin/python teleop_mujoco.py \
  --csv "pruebas/mando-$(date +%Y%m%d-%H%M%S).csv"
```

Haz clic en la ventana **Mando Go2**. Mantén **Espacio** y una sola tecla. Usa **W/S** para avanzar o retroceder, **A/D** para moverte de lado y **Q/E** para girar. Soltar la tecla de dirección o Espacio, perder el foco o pulsar dos direcciones lleva la consigna a cero. **Esc** cierra la prueba. La sesión dura hasta 30 segundos por defecto. Puedes ampliarla con `--seconds` hasta 120 segundos.

### Distancia y destino local

```bash
.venv-a2/bin/python teleop_mujoco.py --distance-m 0.05 \
  --csv "pruebas/avance-5cm-$(date +%Y%m%d-%H%M%S).csv"

.venv-a2/bin/python teleop_mujoco.py --goal 0.25 0.10 \
  --csv "pruebas/destino-$(date +%Y%m%d-%H%M%S).csv"
```

Las distancias están en metros. X es avance, Y es izquierda y el origen es la posición inicial del Go2. La llegada admite 2 cm de error en XY y exige mantenerse en ese radio, con consigna cero y velocidad baja, durante 0,6 s. Es una prueba local en piso plano despejado. El CSV guarda la consigna, la posición respecto al inicio, la velocidad, el error al destino y las caídas. Agrega `--headless` para ejecutar estas pruebas sin visor o usa `--demo --headless` para reproducir la prueba de liberación y pérdida de entrada. [Mediciones de desarrollo](teleop/validation.json).

## Modo sombra dentro del Go2

El comando viaja como una tecla por SSH. El módulo del Go2 recibe `rt/lowstate` por `eth10`, ejecuta la GRU y registra los objetivos calculados en CSV. El proceso mantiene el servicio de movimiento que ya tenga la unidad y crea cero publicadores de `rt/lowcmd`.

### Copiar al Go2 desde la PC

```bash
cd ~/go2-rl-deploy
ssh unitree@192.168.123.18 'mkdir -p ~/go2-shadow/model ~/go2-shadow/pruebas'
scp a2_robot.py a2_policy.py a2_dds.py teleop_input.py unitree@192.168.123.18:go2-shadow/
scp model/a2-p0-student.ts model/manifest-student.json unitree@192.168.123.18:go2-shadow/model/
```

### Preparar Python dentro del Go2 una vez

Si `~/go2-shadow/.venv-a2` ya carga el actor y el SDK, pasa a la prueba. Entra con `ssh unitree@192.168.123.18`. En el módulo ARM64 Ubuntu 20.04, usa un Python 3.11 aislado con `uv`. La descarga requiere acceso a Internet desde el módulo. Los comandos compilan CycloneDDS en el directorio del proyecto.

```bash
cd ~/go2-shadow
mkdir -p deps
command -v git curl cmake gcc g++
```

Si falta alguna de esas herramientas y tienes permiso de administración, instala `git curl cmake build-essential`. Luego crea el entorno.

```bash
curl -fsSL https://astral.sh/uv/install.sh -o /tmp/go2-uv-install.sh
env UV_UNMANAGED_INSTALL="$PWD/deps/uv" sh /tmp/go2-uv-install.sh
deps/uv/uv venv --seed --python 3.11 .venv-a2

git clone --branch 0.10.2 https://github.com/eclipse-cyclonedds/cyclonedds.git deps/cyclonedds
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git deps/sdk
git -C deps/sdk checkout --detach 814556d15970dd2ecf1c9984e845ca02ab07e206
cmake -S deps/cyclonedds -B deps/cyclonedds/build \
  -DCMAKE_INSTALL_PREFIX="$PWD/deps/cyclonedds/install" -DBUILD_TESTING=OFF
cmake --build deps/cyclonedds/build --parallel 2
cmake --install deps/cyclonedds/build

export CYCLONEDDS_HOME="$PWD/deps/cyclonedds/install"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib"
.venv-a2/bin/python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
.venv-a2/bin/python -m pip install ./deps/sdk
.venv-a2/bin/python -c 'from a2_policy import A2Policy; from unitree_sdk2py.utils.crc import CRC; CRC(); A2Policy("student"); print("Actor y SDK OK")'
exit
```

Fuentes de instalación. [Python administrado por uv](https://docs.astral.sh/uv/guides/install-python/) · [Paquetes PyTorch CPU para ARM64](https://download.pytorch.org/whl/cpu/torch/) · [SDK2 Python](https://github.com/unitreerobotics/unitree_sdk2_python/tree/814556d15970dd2ecf1c9984e845ca02ab07e206).

### Abrir el mando desde la PC

```bash
cd ~/go2-rl-deploy
.venv-a2/bin/python teleop_ssh.py unitree@192.168.123.18 --seconds 30
```

Con el Go2 quieto, espera la ventana de mando y prueba las mismas teclas que en MuJoCo. Al soltar una tecla se registra consigna cero. Si dejan de llegar teclas, la última consigna caduca en 250 ms, más el tiempo hasta el siguiente ciclo de lectura. Al cerrar la entrada se registra una última consigna cero y finaliza la captura. El CSV remoto `~/go2-shadow/pruebas/student-teclas-*.csv` incluye `request`, las tres consignas, la edad de la muestra DDS y `policy_ms`. El resumen final debe mostrar `"lowcmd_publishers_created": 0`.

Esta comprobación permite medir telemetría e inferencia en el Go2. Para pedir 5 cm en el piso real faltaría una medición de posición fiable a esa escala, más el ensayo de activación, parada y pérdida de enlace con operador y control del fabricante. La marcha física del alumno sigue pendiente.
