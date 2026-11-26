# Activación del alumno GRU desde una postura observada

Este programa usa una captura de `a2_robot.py observe` como archivo de entrada y ejecuta toda la dinámica en MuJoCo CPU. Conserva el actor TorchScript, el centro articular q0, la escala, la planta binaria P0 y su período de 20 ms. El simulador puede funcionar con el robot desconectado.

## Preparación en Ubuntu

```bash
cd ~/go2-rl-deploy
git pull --ff-only
[ -x .venv-a2/bin/python ] || bash install-panel.sh
mkdir -p pruebas

.venv-a2/bin/python transicion_student.py --help
```

Copia el CSV de observación a `~/transicion_a_de_pie_19700103-121457.csv` y comprueba que exista. Ejecuta las cuatro variantes sin visor:

```bash
.venv-a2/bin/python transicion_student.py \
  --csv "$HOME/transicion_a_de_pie_19700103-121457.csv" \
  --out "pruebas/transicion-$(date +%Y%m%d-%H%M%S)"
```

Para visualizar una variante (46 s de simulación):

```bash
.venv-a2/bin/python transicion_student.py \
  --csv "$HOME/transicion_a_de_pie_19700103-121457.csv" \
  --variant wait-mean --view \
  --out "pruebas/transicion-visor-$(date +%Y%m%d-%H%M%S)"
```

El archivo de entrada permanece en la PC. La salida contiene `summary.json`, un CSV y un JSON por variante y un CSV del asentamiento. El directorio debe ser nuevo.

## Método

- Se valida el orden del modelo y de sus actuadores, los ejes articulares de MuJoCo, el rango de los ángulos y la versión del MJB. La columna SDK ya usa FL, FR, RL, RR, con cadera, muslo y pantorrilla por pata. Se supone que los signos y ceros coinciden con el modelo para esta prueba simulada.
- Se comprueba la primera acción con la fila más cercana a 25 s, el actor recién reiniciado y consigna cero. Las tres referencias del usuario se comparan en grados con una tolerancia de 0,05°.
- Se usa la mediana articular y el cuaternión mediano normalizado de los últimos cinco segundos. La posición XY inicial y la velocidad de la base son cero por hipótesis. Se ajusta la altura para que la planta del pie más bajo toque el piso plano. Se registran los despejes de las otras patas.
- Se simula por separado un segundo con objetivo fijo igual a la postura medida, y se verifica si conserva cuatro apoyos sin contactos ajenos a pies ni más de 5° de desviación. Cada prueba dinámica parte de la reconstrucción geométrica inicial, no del estado deformado en este ensayo.
- `direct` activa el GRU en el primer ciclo. `ramp` mezcla el objetivo medido con el objetivo GRU durante 0,5 s (ajustable con `--blend-s`). `wait` intenta volver a una consigna fija q0 al centrar el mando. `wait-mean` usa como consigna fija la media de los objetivos del último segundo de un ensayo preliminar de cuatro segundos con GRU centrado y entrada gradual en MuJoCo. Esta referencia se genera de nuevo a partir del CSV de entrada.
- En los dos modos de espera, la transición hacia consigna fija se permite al permanecer centrado al menos 0,5 s, con rapidez planar hasta 0,08 m/s, inclinación hasta 15° y al menos tres contactos de pies. Al recibir una consigna no nula se vuelve a mezclar hacia la salida del GRU. El actor sigue actualizándose con observaciones simuladas durante la espera y conserva su estado interno. Las observaciones de acción previa se conservan según A2Policy; durante las mezclas guardan la salida del actor, mientras la planta recibe la consigna interpolada. Esta regla solo pertenece al experimento en simulación.
- Cada variante programa 46 s, con consigna cero de entrada, avance, retroceso, lateral en ambos sentidos, giro en ambos sentidos, intervalos de parada y reanudación del avance. Se registra contacto de tronco, contactos adicionales y caída (altura inferior a 0,16 m, inclinación superior a 60°, o contacto de tronco) por subpaso; se registran cambios de patrón de apoyo y velocidades por decisión.
- El sentido se considera observado si la proyección del desplazamiento en el marco inicial de la maniobra supera 0,02 m en la dirección solicitada, o el giro firmado supera 0,05 rad. Consideramos que un segmento centrado terminó en reposo si, en su último segundo, las medias de rapidez planar, rapidez angular de guiñada y norma de velocidades articulares son como máximo 0,03 m/s, 0,05 rad/s y 0,3 rad/s respectivamente. Estos son criterios de desarrollo.
- Los CSV registran tiempo simulado, objetivos originales y aplicados, articulaciones, contactos y duración de cálculo por ciclo. El resumen separa los 50 Hz nominales de la velocidad de cálculo. Los resultados de una sola postura no verifican la transferencia al hardware.

## Resultado de desarrollo registrado

En la captura de 1.393 muestras y 30 s, las tres referencias de primera acción coincidieron con error inferior a 0,005°. La altura reconstruida fue 0,352 m. Solo el pie FR tocaba el plano al inicio; los otros quedaron a 3,8–7,6 mm. Al mantener la posición medida durante un segundo con el P0 fijo, el error articular máximo fue 27,58° y hubo contacto de pantorrillas traseras. La conservación de esa postura estática no superó el monitor propuesto.

| Variante | Duración | Caídas/Tronco | Otros contactos | Sentidos observados | Segmentos de cero asentados |
| --- | ---: | --- | --- | ---: | ---: |
| Directa | 46 s | 0/0 | ninguno | 7/7 | 0/8 |
| Gradual | 46 s | 0/0 | ninguno | 7/7 | 0/8 |
| Espera q0 | 46 s | 0/0 | pantorrillas traseras | 7/7 | 1/8 |
| Espera objetivo medio | 46 s | 0/0 | ninguno | 7/7 | 8/8 |

La variante de espera con objetivo medio es una candidata de desarrollo simulada. Se ajustó y probó con la misma captura. Los resultados no establecen robustez fuera de ese caso, calibración física ni validez de la transición en el Go2 real.

[Ensayo continuo FixStand → GRU sin reinicializar la física](FixStand-GRU-Continuo.md).
