# Mando oficial Unitree en shadow

`a2_robot.py shadow --remote` lee los 40 bytes de `LowState.wireless_remote` en `rt/lowstate` y entrega al alumno una consigna para inferencia pasiva. El programa usa exclusivamente el suscriptor y CRC de LowState. Los botones se registran sin invocar acciones. Sport conserva el control de la unidad. El programa es incompatible con los modos observe y bench y con la entrada stdin cuando se usa `--remote`. El argumento `--command` se ignora en ese modo. Los modos anteriores conservan sus argumentos y formato de CSV.

## Formato y mapeo

Se utiliza el formato de [wireless_controller.py del SDK oficial, revisión 814556d](https://github.com/unitreerobotics/unitree_sdk2_python/blob/814556d15970dd2ecf1c9984e845ca02ab07e206/example/wireless_controller/wireless_controller.py): máscara de botones uint16 little-endian en los bytes 2–3, cuatro float32 little-endian en los offsets 4, 8, 12 y 20. El resto de los bytes se conserva en hexadecimal sin atribuirles semántica. La convención de signos se contrasta con el [ejemplo RL de Unitree](https://github.com/unitreerobotics/unitree_rl_gym/blob/main/deploy/deploy_real/deploy_real.py). Se espera verificar esa convención en cada mando mediante capturas.

Los valores normalizados usan zona muerta de 0,08 y escala lineal desde el borde de la zona hasta magnitud 1. Se aceptan pequeñas excursiones hasta 1,05 y se recortan a 1. Las escalas corresponden a las consignas del alumno del proyecto.

| Eje | Offset | Consigna derivada para shadow |
| --- | ---: | --- |
| ly | 20 | +0,30 m/s al máximo positivo y −0,20 m/s al máximo negativo |
| lx | 4 | −0,20 m/s al máximo positivo y +0,20 m/s al máximo negativo |
| rx | 8 | −0,30 rad/s al máximo positivo y +0,30 rad/s al máximo negativo |
| ry | 12 | Solo registro |

## Capturar en el Go2

Usa la instalación existente en `~/proyecto_go2`, `.venv311` y `eth10`. Copia únicamente `a2_robot.py` y `remote_input.py` de la misma revisión, respaldando cualquier versión local anterior. Deja Sport en su estado actual. Una captura centrada de 10 s verifica el origen de los ejes según lo recibido:

```bash
cd ~/proyecto_go2
export CYCLONEDDS_HOME="$HOME/cyclonedds_ws/install/cyclonedds"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p pruebas
out=$(mktemp -d "$PWD/pruebas/remote-centro.XXXXXX")
.venv311/bin/python a2_robot.py shadow --remote --iface eth10 \
  --policy-update student --seconds 10 --csv "$out/registro.csv"
```

Repite con `--seconds 20` y un directorio nuevo para registrar una maniobra breve mediante el mando de fábrica. Mueve un eje cada vez y retorna al centro entre deflexiones; evita combinaciones de botones que alteren el estado de Sport. Usa el procedimiento habitual de prueba física del laboratorio. El programa solo registra lo que recibe. El informe incluye mínimos y máximos por eje, mediana de muestras dentro de la zona central y recuento de deflexiones positivas/negativas aisladas. La correspondencia con las direcciones físicas requiere conocer qué hizo el operador.

## Evidencia y estado de enlace

El CSV contiene ticks, edad desde recepción DDS local hasta selección de muestra, intervalo real entre selecciones, duración de inferencia, ejes crudos, máscara y nombres de botones, bytes del mando, estado de decodificación, tiempo con bytes sin cambio, tres consignas, IMU, posiciones y velocidades, tau_est y objetivos de posición GRU. Las coordenadas y objetivos siguen el orden del actor. Los objetivos asumen signos y ceros coincidentes para inferencia pasiva. Un intervalo de 20 ms es nominal, la ejecución registra el valor efectivo. El primer intervalo queda vacío. El JSON adjunto (`.summary.json`) resume tiempos, rangos y motivos de cierre.

- `centered_axes_link_unknown` indica ejes en zona muerta de un paquete decodificable y no completamente vacío.
- `active_axes_link_unknown` indica al menos un eje fuera de la zona, aunque ry por sí solo no alimenta consignas.
- `all_zero_payload_link_unknown` diferencia 40 bytes nulos y deriva consigna cero. Podría corresponder a un mando centrado o a información ausente.
- `invalid_axes` o `invalid_length` representan datos incompatibles con el decodificador. La consigna derivada es cero y se conserva el diagnóstico.
- `lowstate_timeout_or_tick_stalled` o `lowstate_stale` cierran la captura con estado fallido y conservan sus registros parciales. CRC incorrecto también produce fallo.

El SDK no da un contador de secuencia de radio, indicador de conexión o timestamp propio del mando en esos campos decodificados. Los ticks y la edad demuestran frescura de LowState, mientras que un paquete repetido puede ser una palanca mantenida, un mando centrado o una pérdida de actualización. El estado de radio siempre se informa como no verificado. El comando derivado se calcula para el actor, sin funcionar como watchdog físico.

## Pruebas de CPU

Desde el entorno Python que ya tiene instalado el SDK:

```bash
python -m unittest -v test_remote_shadow
```

Incluye los cuatro ejes por separado en ambos sentidos, escala intermedia, centro, los 16 botones, paquetes inválidos y repetidos, pérdida de telemetría y protección de modos. La prueba de CLI intercepta y rechaza construcción de LowCmd, publicadores, cliente Sport y MotionSwitcher, y verifica que solo se abre el suscriptor. Se utilizó además un DDS loopback aislado con LowState sintético y los pesos reales del GRU. Queda pendiente la captura con el mando de la unidad.
