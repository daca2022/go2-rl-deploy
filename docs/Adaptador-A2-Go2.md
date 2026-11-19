# A2/P0 por Ethernet

El GRU corre en la PC Ubuntu 22.04. SDK2 Python y CycloneDDS intercambian mensajes por Ethernet con el Go2. Aunque el robot tenga Ubuntu 20.04 con ROS 2 Foxy, la PC puede ejecutar este cliente directamente por DDS. El procedimiento usa el firmware y los servicios Unitree que exponga el robot. Foxy es la distribución de ROS 2, Ubuntu 20.04 es el sistema operativo.

El adaptador toma 47 observaciones de `rt/lowstate` y ejecuta una inferencia a 50 Hz. Conserva la memoria de la GRU durante el ensayo y la reinicia al comienzo. Las salidas son objetivos de posición P0. El orden del actor FL, FR, RL, RR se convierte al orden SDK FR, FL, RR, RL antes de escribir `rt/lowcmd`. Se usa CRC del SDK en los mensajes. En la prueba de banco, el bucle intenta publicar a 500 Hz sosteniendo el objetivo entre inferencias y vigila retrasos. La frecuencia efectiva sobre Ethernet se mide en la PC del ensayo.

Los comandos de esta guía usan U2000 de manera predeterminada. Añade `--policy-update 4000` al proceso `policy` de `a2_sim.py` y a los modos `shadow` o `bench` de `a2_robot.py` para cargar U4000. El perfil de banco y sus límites corresponden a tu unidad. [Comandos de U4000](U4000-Go2.md).

## Preparar la PC

Si ya tienes el repositorio, usa `git pull --ff-only` dentro de él y pasa a la instalación.

```bash
sudo apt update
sudo apt install git python3-venv python3-dev build-essential cmake libgl1 libglfw3
git clone https://github.com/daca2022/go2-rl-deploy.git
cd go2-rl-deploy
python3 -m venv .venv-a2
.venv-a2/bin/pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
.venv-a2/bin/pip install -r requirements-sim.txt 'opencv-python==4.11.0.86'
mkdir -p deps pruebas
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git deps/sdk
git -C deps/sdk checkout 814556d15970dd2ecf1c9984e845ca02ab07e206
git clone --branch 0.10.2 https://github.com/eclipse-cyclonedds/cyclonedds.git deps/cyclonedds
cmake -S deps/cyclonedds -B deps/cyclonedds/build \
  -DCMAKE_INSTALL_PREFIX="$PWD/deps/cyclonedds/install"
cmake --build deps/cyclonedds/build --parallel 2
cmake --install deps/cyclonedds/build
CYCLONEDDS_HOME="$PWD/deps/cyclonedds/install" .venv-a2/bin/pip install -e deps/sdk
.venv-a2/bin/python -c 'import torch, mujoco; from unitree_sdk2py.utils.crc import CRC; CRC(); print("OK")'
```

El SDK se instala en modo editable para usar sus bibliotecas CRC tal como vienen en el repositorio. Ejecuta estos comandos en una terminal sin haber cargado otro entorno de ROS. Si ya existe `deps/sdk` o `deps/cyclonedds`, reúsalo tras confirmar la revisión anterior.

## 1. MuJoCo por DDS

En dos terminales abiertas en el repositorio, primero inicia el puente y luego la política. El puente espera al actor durante el primer ciclo. Usa un nombre de CSV distinto en cada ensayo.

```bash
.venv-a2/bin/python a2_sim.py bridge --view --csv pruebas/a2-dds-lateral.csv
```

```bash
.venv-a2/bin/python a2_sim.py policy --command lateral
```

También puedes usar forward, reverse o yaw. Omite `--view` para ejecutar sin ventana. El puente y el actor usan dominio 19 e interfaz lo. El simulador solo avanza cuando recibe el comando del ciclo correspondiente. La entrega se comprobó con el modelo P0 compilado utilizado en el laboratorio. El puente de esta prueba es el incluido en el repositorio.

## 2. Go2 físico, captura y política pasiva

Conecta la Ethernet de desarrollo. En Ubuntu configura manualmente `192.168.123.99/24` en esa interfaz si el Go2 usa la subred estándar. Deja gateway y DNS vacíos en ese enlace. Identifica la interfaz real con `ip -br link` y comprueba su dirección con `ip -br addr`. Usa la guía Ethernet si la dirección del robot fue personalizada.

```bash
IFACE=enp3s0
.venv-a2/bin/python a2_robot.py observe --iface "$IFACE" --seconds 10 \
  --csv pruebas/a2-lowstate.csv
```

Confirma que el tick avanza, llegan las 12 posiciones, velocidades y torque estimado, y la IMU reporta valores coherentes. Identifica la variante, versión de firmware y las posiciones de referencia con el Go2 quieto o sostenido. La captura comprueba el CRC y la antigüedad de las muestras.

```bash
.venv-a2/bin/python a2_robot.py shadow --iface "$IFACE" --seconds 10 \
  --command forward --csv pruebas/a2-shadow.csv
```

En shadow, el GRU calcula objetivos y los escribe en el CSV. Este flujo solo abre el suscriptor de `rt/lowstate`. Los objetivos pasivos asumen que el signo, cero y marco de IMU del SDK coinciden con el entrenamiento. Sirven para inspección inicial. El modo banco aplica el mapeo verificado del perfil.

## 3. Go2 físico, primer pulso A2 en banco

Para probar los 12 objetivos reales, usa el Go2 sostenido de manera estable, patas libres y operador junto al mando de parada. Confirma primero la respuesta del paro físico y cómo responde el firmware al perder comandos en ese banco. Completa el perfil con datos de tu unidad y verifica articulaciones e IMU. Luego desactiva manualmente el controlador Sport según el procedimiento del fabricante. El script comprueba el resultado con MotionSwitcher y aborta si un servicio sigue activo. Cierra otros emisores de `rt/lowcmd`.

```bash
cp docs/a2-bench-profile.template.json pruebas/a2-bench-profile.json
```

Completa las 12 entradas de cada vector en el orden de `joint_names`. El perfil se entrega con campos pendientes para introducir los valores comprobados. El mapeo usa `q_actor = sign * (q_sdk - sdk_zero_rad)` y el inverso al enviar. Los límites se expresan en radianes en el marco del actor. Usa ganancias comprobadas en banco, límites de desplazamiento y de torque estimado de tu protocolo. El programa verifica también su envolvente máxima de banco. Usa `frames_verified=true` una vez confirmado el sentido, cero, orden, cuaternión wxyz y giroscopio en el marco de la base.

Con el perfil completo, el primer pulso dura como máximo 0,5 s. La entrada exige una postura cercana a la pose nominal. El adaptador restringe objetivos y vigila edad de las muestras, inclinación, velocidad articular y plazos del bucle. Al salir intenta emitir amortiguación durante 0,2 s. El paro físico es quien protege si cae el proceso, se desconecta el cable o un comando no llega.

```bash
.venv-a2/bin/python a2_robot.py bench --iface "$IFACE" --seconds 0.5 \
  --command forward --bench-profile pruebas/a2-bench-profile.json \
  --csv pruebas/a2-banco-01.csv
```

Registra en la bitácora los objetivos enviados y medidos, retrasos, torque estimado y confirmación de parada. Después del banco queda comprobar la frecuencia real bajo carga, saturación y repetibilidad. Caminar en el piso requiere puesta en pie y transición de control validadas, watchdog y paro físico probados, y medición externa de velocidad o distancia para evaluar el seguimiento si Sport está desactivado.

## Referencias

- [Unitree SDK2 Python y procedimiento de control de bajo nivel](https://github.com/unitreerobotics/unitree_sdk2_python/tree/814556d15970dd2ecf1c9984e845ca02ab07e206)
- [Configuración de red Unitree](https://github.com/unitreerobotics/unitree_ros2#connect-to-unitree-robot)
- [DDS en Unitree MuJoCo](https://github.com/unitreerobotics/unitree_mujoco)
