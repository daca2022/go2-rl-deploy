# Unitree Go2 por Ethernet
Guía de puesta en marcha desde Ubuntu 22.04 · A2/P0 · GRU de 128

## Informe técnico de entrega

- [Informe PDF](docs/Informe-Go2.pdf) y [fuente LaTeX](docs/Informe-Go2.tex)
- [Draw.io de arquitectura y ensayos](docs/Go2-Entrega.drawio)
- [Bitácora Excel](docs/Bitacora-Go2.xlsx) y [resultados en MuJoCo por DDS](docs/Prueba-A2-DDS.json)

El fuente LaTeX es autocontenido. Para regenerar el PDF con TeX Live, ejecuta `latexmk -pdf docs/Informe-Go2.tex` desde el repositorio.

## Inicio rápido con el panel

En Ubuntu 22.04 abre una terminal en el escritorio de la PC del robot. Instala Git si hace falta. El panel abre localmente y funciona con CPU.

```bash
sudo apt update
sudo apt install git
git clone https://github.com/daca2022/go2-rl-deploy.git
cd go2-rl-deploy
bash install-panel.sh
bash abrir-panel.sh
```

Si ya tienes el repositorio, usa `git pull --ff-only` dentro de la carpeta existente. Después de instalar, para volver a abrir la ventana basta con `bash abrir-panel.sh`.

Desde la ventana puedes seleccionar avance, retroceso, lateral izquierdo y giro. MuJoCo usa el GRU. En el robot, la lectura de telemetría y el modo sombra son de solo lectura. El movimiento en piso que ofrece el panel usa Sport de fábrica. El modo GRU en banco requiere el perfil calibrado de tu unidad, Sport desactivado y el perro sostenido con patas libres. [Guía del panel y primera conexión](docs/Panel-Go2.md).

## 1. Qué hay en el paquete
El actor exportado corresponde al checkpoint A2/P0 2.000, semilla 7. El archivo .ts contiene la red y su normalización. El .mjb contiene la planta P0 compilada para MuJoCo 3.5.0. El manifiesto fija las huellas, el orden de las 12 articulaciones y la escala. La inferencia exportada se cotejó durante 32 pasos recurrentes con el actor original.

El ensayo local usa la política entrenada. El ensayo físico usa el controlador Sport de fábrica. El puente oficial Unitree MuJoCo implementa el transporte DDS de bajo nivel en simulación. El adaptador de 47 observaciones y 12 objetivos articulares se comprobó con mensajes del SDK en MuJoCo. La guía del adaptador describe las comprobaciones físicas de tu Go2.

## 2. Descargar y probar en MuJoCo
En la PC Ubuntu 22.04 de 64 bits, instala Git y entornos virtuales de Python. Puedes clonar el repositorio público sin cuenta de GitHub.

```bash
sudo apt update
sudo apt install git python3-venv python3-dev build-essential cmake libgl1 libglfw3
git clone https://github.com/daca2022/go2-rl-deploy.git
cd go2-rl-deploy
python3 -m venv .venv-sim
.venv-sim/bin/pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
.venv-sim/bin/pip install -r requirements-sim.txt
mkdir -p pruebas
.venv-sim/bin/python replay.py forward --view --csv pruebas/sim-forward.csv
```

Para probar de lado, usa `lateral`. También están `reverse` y `yaw`. Usa un nombre CSV nuevo en cada prueba. Omite `--view` en una PC sin ventana gráfica. El programa registra consigna, velocidad medida por eje, altura y un indicador de caída para esta vista. Reporta error cuadrático medio de velocidad en el plano y duración. Los 20 s de esta prueba sirven para revisar la exportación y el movimiento.

## 3. Instalar el SDK Python
Usa un entorno virtual independiente. El SDK fijado declara CycloneDDS 0.10.2. Si pip pide CYCLONEDDS_HOME, compila CycloneDDS localmente con el bloque de abajo y vuelve a intentar.

```bash
python3 -m venv .venv-sdk
mkdir -p deps
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git deps/sdk
git -C deps/sdk checkout 814556d15970dd2ecf1c9984e845ca02ab07e206
.venv-sdk/bin/pip install ./deps/sdk
```

```bash
git clone --branch 0.10.2 https://github.com/eclipse-cyclonedds/cyclonedds.git deps/cyclonedds
cmake -S deps/cyclonedds -B deps/cyclonedds/build \
  -DCMAKE_INSTALL_PREFIX="$PWD/deps/cyclonedds/install"
cmake --build deps/cyclonedds/build --parallel 2
cmake --install deps/cyclonedds/build
CYCLONEDDS_HOME="$PWD/deps/cyclonedds/install" .venv-sdk/bin/pip install ./deps/sdk
```

## 4. Conectar, leer y mover con Sport
1. Conecta el cable al puerto de desarrollo del Go2. Verifica que tu variante y firmware exponen el SDK y el servicio Sport. Anota modelo, firmware y operador en la bitácora.
2. Ejecuta `ip -br link` y elige la Ethernet que aparece UP tras conectar. En los ajustes de red de Ubuntu, asigna IPv4 manual 192.168.123.99/24 a esa interfaz según el esquema oficial. Deja gateway y DNS vacíos para ese enlace directo. Si la red del robot fue personalizada, usa su subred. Comprueba la interfaz con `ip -br addr`.
3. Con el Go2 quieto y el servicio Sport activo, verifica primero recepción. Sustituye enp3s0 por la interfaz real.

```bash
IFACE=enp3s0
.venv-sdk/bin/python robot.py --iface "$IFACE" --seconds 10 \
  --csv pruebas/go2-quieto.csv
```

La conexión se confirma al recibir telemetría reciente en el CSV. Si falta, revisa enlace, IPv4, interfaz elegida, versión del firmware, servicio Sport y que otro entorno ROS no altere DDS. El SDK Python usa DDS directamente y ROS 2 es opcional.

4. Para el primer movimiento, despeja piso plano, deja el mando físico listo para detener y pon el Go2 de pie con ese mando. Trabaja con un operador junto al mando y una sola fuente de comandos de movimiento. Ejecuta el pulso corto y confirma parada física antes de repetir.

```bash
.venv-sdk/bin/python robot.py --iface "$IFACE" --seconds 0.5 \
  --pulse forward --arm --csv pruebas/go2-avance-01.csv
```

Puedes elegir reverse, left, right o yaw en pruebas separadas. Para teleoperación continua inicial usa el mando físico de Unitree con el capturador en modo lectura. El pulso de terminal pide StopMove al concluir o ante una interrupción. Si se pierde el cable o el equipo se apaga, la orden de parada por software puede no llegar. Usa el mando físico según el procedimiento del equipo y comprueba la parada con observación directa. Move emplea una llamada sin respuesta. Su código y tiempo de envío pertenecen al PC, mientras que movimiento y frenado se comprueban con telemetría y observación.

## 5. Recorrido de datos y futuro control A2
Abre docs/Go2-Ethernet.drawio en diagrams.net. En el ensayo real actual, el PC escucha rt/sportmodestate con SDK2 Python en el dominio DDS 0 y envía Sport Move y StopMove al servicio de fábrica. En el simulador oficial usa dominio separado y loopback. El replay del paquete ejecuta MuJoCo localmente dentro del mismo proceso.

El adaptador A2/P0 ya está disponible en a2_robot.py. Se comprobó por DDS en MuJoCo con a2_sim.py. La [guía del adaptador](docs/Adaptador-A2-Go2.md) incluye captura de LowState, inferencia en modo pasivo y el primer pulso físico sobre banco con un perfil verificado. Los tópicos de bajo nivel se integran a 50 Hz en el actor. La aceptación física y el ensayo de marcha en el piso quedan pendientes.

## 6. Guardar evidencia
Usa docs/Bitacora-Go2.xlsx para una fila por ensayo. Conserva los CSV en pruebas/ y anota su nombre. Para MuJoCo registra RMSE por consigna y caídas. Para el Go2 anota velocidad/posición que reporta el SDK, tiempos, errores, parada observada y distancia medida. Confirma el marco de la velocidad física antes de calcular RMSE contra consignas en el marco del cuerpo. El tiempo local de SDK y la edad de la muestra se registran como valores distintos. Marca como pendiente una señal que el equipo aún no mida.

## Fuentes oficiales
- SDK Python de Unitree https://github.com/unitreerobotics/unitree_sdk2_python/tree/814556d15970dd2ecf1c9984e845ca02ab07e206
- Red de control Unitree https://github.com/unitreerobotics/unitree_ros2#connect-to-unitree-robot
- Puente de simulación https://github.com/unitreerobotics/unitree_mujoco
