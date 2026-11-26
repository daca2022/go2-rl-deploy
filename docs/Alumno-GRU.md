# Go2 con alumno GRU

El alumno se ajustó a partir del A2/P0 U4000 con etiquetas del maestro U4300. El actor TorchScript de este paquete recibe 47 observaciones y devuelve 12 objetivos articulares mediante el adaptador P0. La opción `--policy-update student` selecciona ese alumno. Las opciones `2000` y `4000` cargan las referencias PPO.

En la prueba reservada de MuJoCo el alumno completó 20/20 episodios de 20 s sin caídas ni contacto del cuerpo. También completó avance, retroceso, lateral y giro por DDS local. [Resultados reservados](student/reserved-summary.json) · [40 episodios emparejados en CSV](student/reserved-episodes.csv) · [Prueba DDS](student/sim-validation.json) · [Video de avance](student/Go2-alumno-GRU-avance.mp4).

## Preparar Ubuntu 22.04

En la PC que se conectará al Go2, ejecuta el instalador desde una terminal.

```bash
cd ~
git clone https://github.com/daca2022/go2-rl-deploy.git
cd go2-rl-deploy
bash install-panel.sh
mkdir -p pruebas
```

Si ya tienes una copia, entra a ella y usa `git pull --ff-only`. Si tu entorno `.venv-a2` ya funciona, puedes reutilizarlo.

El instalador crea `.venv-a2` e instala MuJoCo, PyTorch CPU, CycloneDDS y el SDK2 Python. El cliente usa DDS directamente por Ethernet. La PC puede usar Ubuntu 22.04 aunque el Go2 ejecute ROS 2 Foxy en Ubuntu 20.04.

## Verlo caminar en MuJoCo

```bash
cd ~/go2-rl-deploy
.venv-a2/bin/python replay.py forward --policy-update student --view \
  --csv "pruebas/student-mujoco-$(date +%Y%m%d-%H%M%S).csv"
```

Usa `reverse`, `lateral` o `yaw` en lugar de `forward` para comprobar las otras consignas. El visor ejecuta un episodio de 20 s. Para usar el panel, ejecuta `bash abrir-panel.sh`, selecciona `student` y marca la opción de visualización de MuJoCo.

[Mando por teclado, avance de 5 cm y destinos en MuJoCo](Teleoperacion-GRU.md).

## Go2 real por Ethernet

Conecta el cable de desarrollo y deja el Go2 quieto. Usa `ip -br addr` para identificar la interfaz. Si tu unidad conserva la red estándar de Unitree, configura `192.168.123.99/24` en la PC, sin gateway en ese enlace. Cambia `enp3s0` por el nombre de tu interfaz.

```bash
cd ~/go2-rl-deploy
IFACE=enp3s0
.venv-a2/bin/python a2_robot.py observe --iface "$IFACE" --seconds 10 \
  --csv "pruebas/student-lowstate-$(date +%Y%m%d-%H%M%S).csv"
.venv-a2/bin/python a2_robot.py shadow --policy-update student \
  --iface "$IFACE" --seconds 10 --command forward \
  --csv "pruebas/student-shadow-$(date +%Y%m%d-%H%M%S).csv"
```

[Lectura del mando oficial Unitree en shadow](Mando-Unitree-Shadow.md).

Los modos de observación y sombra reciben `rt/lowstate`. El modo sombra calcula y guarda en CSV los objetivos del alumno sin enviar `rt/lowcmd`. Comprueba que avanza el tick, que las muestras son recientes y que IMU y articulaciones coinciden con los marcos del modelo.

### SSH por Ethernet

El SDK se ejecuta en la PC Ubuntu conectada al Go2 y usa DDS. SSH sirve para abrir una terminal remota. Si quieres entrar **desde tu laptop a la PC Ubuntu**, conecta ambos equipos a una red común o a un enlace Ethernet con direcciones diferentes de la misma subred. La PC puede usar Wi-Fi o una segunda interfaz para la laptop y reservar el otro puerto para el Go2.

En la PC Ubuntu habilita el servicio y anota la IPv4 de la interfaz que comparte con la laptop.

```bash
sudo apt install openssh-server
sudo systemctl enable --now ssh
ip -br addr
```

Desde la laptop, cambia los dos valores por el usuario y la IP de la **PC Ubuntu**.

```bash
PC_USER=usuario_pc
PC_IP=192.168.1.50
ssh -o ConnectTimeout=5 "$PC_USER@$PC_IP"
```

Para entrar directamente al Go2 por el cable, usa `ssh usuario_go2@IP_DEL_GO2` solo si la unidad tiene un servidor SSH activo y tienes una cuenta autorizada. Usa la dirección asignada al robot según su configuración. `192.168.123.99` es el ejemplo de IP de la **PC** en la red del robot. [OpenSSH en Ubuntu](https://ubuntu.com/server/docs/how-to/security/openssh-server/) · [Red de desarrollo de Unitree](https://github.com/unitreerobotics/unitree_ros2#connect-to-unitree-robot)

### Ensayo del alumno en banco

Con la unidad sostenida, las patas libres y un operador al mando de parada, verifica el perfil de tu unidad, los signos y ceros, el paro físico y la pérdida de enlace. Completa la plantilla con valores medidos siguiendo [la guía del adaptador](Adaptador-A2-Go2.md#3-go2-físico-primer-pulso-a2-en-banco). El adaptador verifica que Sport esté desactivado antes de publicar objetivos en banco.

```bash
cp -n docs/a2-bench-profile.template.json pruebas/a2-bench-profile.json
# Ejecuta las siguientes líneas cuando el perfil ya esté medido y verificado.
.venv-a2/bin/python a2_robot.py bench --policy-update student \
  --iface "$IFACE" --seconds 0.5 --command forward \
  --bench-profile pruebas/a2-bench-profile.json \
  --csv "pruebas/student-banco-$(date +%Y%m%d-%H%M%S).csv"
```

La marcha del alumno en el piso requiere verificar primero el banco, el traspaso de control desde la postura de pie, y la respuesta al paro y a la pérdida de enlace.

### Marcha física con Sport

Para comprobar la marcha con el controlador de fábrica, el Go2 debe estar de pie en plano, con Sport activo, un espacio despejado y el operador con el mando de parada. Cierra la prueba de banco y cualquier emisor de bajo nivel. El panel ofrece el modo Sport. También puedes lanzar un pulso corto desde la terminal.

```bash
.venv-a2/bin/python robot.py --iface "$IFACE" --seconds 0.5 --pulse forward --arm \
  --csv "pruebas/sport-avance-$(date +%Y%m%d-%H%M%S).csv"
```

Fuentes oficiales. [SDK2 Python de Unitree](https://github.com/unitreerobotics/unitree_sdk2_python/tree/814556d15970dd2ecf1c9984e845ca02ab07e206) · [Configuración de red Unitree](https://github.com/unitreerobotics/unitree_ros2#connect-to-unitree-robot)
