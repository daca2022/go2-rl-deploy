# Panel Go2 en Ubuntu 22.04

El panel abre una ventana local de escritorio. La instalación prepara el SDK2 Python, CycloneDDS, PyTorch CPU y MuJoCo en `.venv-a2`. El modelo incluido es el A2/P0 de la actualización 2.000. Las consignas entrenadas disponibles son avance, retroceso, lateral izquierdo y giro.

```bash
sudo apt update
sudo apt install git
git clone https://github.com/daca2022/go2-rl-deploy.git
cd go2-rl-deploy
bash install-panel.sh
bash abrir-panel.sh
```

Si ya clonaste el repositorio, entra en esa carpeta y usa `git pull --ff-only`. Para volver a abrir la ventana, usa `bash abrir-panel.sh`. La primera instalación puede tardar al descargar PyTorch y compilar CycloneDDS.

## Simulación

1. Elige **MuJoCo · política GRU** y una consigna. Deja activado **Abrir visor MuJoCo** para ver el trote, o desactívalo para recolectar datos más rápido.
2. Pulsa **Iniciar prueba**. El panel arranca el simulador y el actor automáticamente en loopback.
3. Al terminar, revisa los segundos simulados y el error de velocidad. **Abrir resultados** abre la carpeta que guarda el CSV, más el registro de cada proceso.

## Robot físico

1. Conecta la Ethernet de desarrollo. En la configuración de red de Ubuntu, pon `192.168.123.99/24` en esa interfaz si tu Go2 usa la red de fábrica. Deja gateway y DNS vacíos en ese enlace. Para una subred personalizada, usa la configuración de tu unidad.
2. Selecciona la Ethernet en el panel y pulsa **Actualizar**. El estado muestra si hay enlace y qué IPv4 tiene. Elige **Go2 · comprobar telemetría** en **Prueba**. Pulsa **Iniciar prueba** y verifica que lleguen muestras.
3. Prueba **GRU en sombra** con el robot quieto. Compara en el CSV las posiciones y velocidades articulares medidas con los objetivos de la política. Este modo lee del Go2 y registra inferencia.
4. Para un movimiento inicial en piso, pon al Go2 de pie con el mando, mantén Sport activo y despeja el área. Elige **Pulso con Sport**, la consigna y confirma el movimiento. El pulso dura hasta 0,5 s. Para teleoperación continua usa el mando, con el panel en modo de lectura. La parada física está a cargo del operador con el mando, sobre todo si se pierde Ethernet.
5. Selecciona **Pulso GRU en banco** cuando hayas completado el perfil y validado postura, IMU, articulaciones, paro y pérdida de enlace. Mantén el Go2 sostenido y desactiva Sport siguiendo el procedimiento de Unitree. Usa **Elegir perfil** e inicia un pulso. El software comprueba que no haya un modo de movimiento activo y limita la prueba. [Procedimiento y perfil de banco](Adaptador-A2-Go2.md#3-go2-físico-primer-pulso-a2-en-banco).

Cada ensayo nuevo genera nombres únicos en `pruebas/`. El botón **Detener** solicita a los procesos actuales terminar por su ruta normal. En una prueba física, confirma siempre el cese de movimiento en el robot. Usa [la bitácora de ensayos](Bitacora-Go2.xlsx) para registrar lo que observaste junto con el CSV.

## Estado físico de la política

El recorrido DDS de la política se probó en MuJoCo. La marcha en piso con el GRU queda pendiente hasta validar la primera prueba en banco, frecuencia efectiva, respuesta ante pérdida de comandos y transición desde la postura inicial en esa unidad. El panel ofrece en piso pulsos de Sport con la misma dirección seleccionada y velocidades reducidas. Sus resultados corresponden al controlador de fábrica.
