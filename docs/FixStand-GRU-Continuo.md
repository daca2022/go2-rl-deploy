# FixStand y GRU en una sola corrida de MuJoCo

El ensayo anterior permanece disponible en `transicion_student.py`. El nuevo `transicion_continua.py` compara dos modos de sostén desde la misma reconstrucción del CSV físico. Cada corrida evaluada conserva un único `MjData` desde la inicialización hasta el final. La calibración del objetivo de espera wait-mean se hace por separado, con el mismo método de la prueba publicada; no forma parte de la corrida evaluada y su estado no se copia.

## Ejecutar en la PC Ubuntu

```bash
cd ~/go2-rl-deploy
git pull --ff-only
python3 -m venv .venv-sim
.venv-sim/bin/pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
.venv-sim/bin/pip install -r requirements-sim.txt
mkdir -p pruebas

.venv-sim/bin/python transicion_continua.py \
  --csv "$HOME/transicion_a_de_pie_19700103-121457.csv" \
  --out "pruebas/continuo-$(date +%Y%m%d-%H%M%S)"
```

Para ver la corrida completa, incluida la fase FixStand, en una ventana continua:

```bash
.venv-sim/bin/python transicion_continua.py \
  --csv "$HOME/transicion_a_de_pie_19700103-121457.csv" \
  --case stiffness --view \
  --out "pruebas/continuo-visor-$(date +%Y%m%d-%H%M%S)"
```

## Diagnóstico en simulación

La mediana de las 232 muestras finales reproduce la geometría articular de la captura bajo la hipótesis de signos y ceros coincidentes. La altura se reconstruye dejando la planta más baja sobre un plano horizontal. Se observa una base casi nivelada y alturas relativas de plantas FL 3,75 mm, FR 0 mm, RL 4,79 mm y RR 7,57 mm. P0 aporta una masa de 15,21 kg y un peso de 149,17 N. En el estado inicial las 12 fuerzas de actuador son cero por construcción y solo FR tiene contacto. La fuerza vertical inicial del contacto es 12,27 N. En la captura original, `tau_est` muestra esfuerzo durante el sostén, aunque no revela las consignas de Sport.

Se comparan 3 s con P0 fijo y 3 s con mayor rigidez de los servos **solo en MuJoCo**. El segundo modo usa la referencia articular medida y amortiguación aumentada en proporción a la raíz cuadrada del factor de rigidez, sin alterar los límites de fuerza del modelo. El objetivo es disminuir el error necesario para desarrollar esfuerzo de soporte bajo gravedad. El ensayo guarda el esfuerzo y el término de sesgo de cada articulación, la fuerza vertical por pie y en otros contactos, el estado y los objetivos. La captura de torque físico se utiliza únicamente como referencia comparativa. Las fuerzas de MuJoCo corresponden a la evaluación dinámica más reciente, hasta un subpaso de 5 ms anterior a la posición de la fila.

| Métrica tras 3 s | P0 fijo | Sostén simulado |
| --- | ---: | ---: |
| Altura de base | 0,241 m | 0,337 m |
| Máxima desviación articular de la captura | 27,58° | 3,76° |
| Deriva horizontal | 22,81 cm | 1,85 cm |
| Pies en apoyo al final | 4 | 4 |
| Fuerza vertical total | 149,18 N | 149,18 N |
| Fuerza vertical ajena a los pies | 55,51 N | 0 N |
| Contacto de pantorrillas | sí | no |
| Contacto de tronco | no | no |
| FixStand | falla | pasa |

El criterio de FixStand exige los 3 s completos, ningún contacto ajeno a los pies o caída, cuatro pies durante todo el último segundo, máximo error de 5°, y velocidades medias finales de base y articulaciones acotadas. La base P0 fija no pasa, por lo que se detiene antes de activar la política.

## Handoff y resultados

En la variante que pasa FixStand, el actor recién reiniciado recibe las observaciones del mismo estado físico al segundo 3, sin restaurar posición o velocidad. Se mezcla desde el último objetivo de sostén y se recuperan los parámetros P0 originales durante la entrada de 0,5 s. La primera consigna aplicada es idéntica a la última de FixStand. Los objetivos del propio alumno, su escala y su q0 permanecen originales. Después se utiliza el protocolo wait-mean del ensayo anterior completo, incluidos avance, retroceso, dos laterales, dos giros, retorno a cero y reanudación. El resultado de desarrollo con esta captura fue 49 s continuos sin caída ni contacto ajeno a los pies, siete sentidos correctos y ocho segmentos de cero asentados. La deriva de frenado llegó a 11,6 cm. La postura inmediatamente anterior y posterior al primer ciclo GRU se guarda en el JSON junto con la salida original y la consigna aplicada.

## Señales y reproducibilidad

El CSV original aporta q, dq, IMU, gyro, tick y estimaciones de torque. El SDK LowState también declara `foot_force` y `foot_force_est`, que quedaron fuera de esta captura. Sus unidades, orden y comportamiento requerirían comprobación en la unidad. La altura absoluta, el desplazamiento del cuerpo y la fuerza de contacto exacta provienen aquí de MuJoCo; en un ensayo físico necesitarían estimación o instrumentación. Las consignas internas de Sport no se conocen.

Cada ejecución guarda `summary.json`, un JSON por caso y CSV de sostén y marcha. La traza de marcha usa tiempos absolutos de simulación y permite cotejar el último estado de FixStand con la primera decisión. Esta prueba de desarrollo corresponde a una única captura y una planta simulada. El sostén con parámetros de simulación no constituye una calibración de servos del Go2 ni un controlador para uso físico.

[Reproducir las consignas grabadas con el mando](Reproducir-Mando-MuJoCo.md).
