# Comparación de reactivación espera → GRU

Se conserva la transición inicial FixStand → GRU de 0,5 s, el retorno a espera de 0,5 s, la planta P0 restaurada tras FixStand, la escala, q0 y los pesos del alumno. Se modifica exclusivamente la duración de mezcla al salir de espera por una consigna no nula.

El objetivo de espera se calcula una vez desde la primera captura. Todas las corridas parten de la segunda captura y usan la misma entrada del mando remuestreada a 20 ms. La corrida centrada de control tiene la misma duración y no recibe pulsos.

## Ejecutar

```bash
cd ~/go2-rl-deploy
git pull --ff-only
mkdir -p pruebas
.venv-sim/bin/python comparar_reactivacion.py \
  --calibration "$HOME/transicion_a_de_pie_19700103-121457.csv" \
  --initial "$HOME/transicion_02_19700103-130220.csv" \
  --remote-csv "$HOME/go2_mando_ejes.csv" \
  --out "pruebas/reactivacion-$(date +%Y%m%d-%H%M%S)"
```

Visualizar la variante seleccionada en este caso:

```bash
.venv-sim/bin/python reproducir_mando.py \
  --calibration "$HOME/transicion_a_de_pie_19700103-121457.csv" \
  --initial "$HOME/transicion_02_19700103-130220.csv" \
  --remote-csv "$HOME/go2_mando_ejes.csv" \
  --reactivation-s 0.10 --view \
  --out "pruebas/reactivacion-visor-$(date +%Y%m%d-%H%M%S)"
```

## Métricas y elección

El resumen guarda por maniobra la integral de la consigna original con retención entre muestras, la integral a 50 Hz, respuesta firmada en el marco inicial de la maniobra, máximo salto de objetivo, máxima inclinación, apoyos y contactos. Para el período posterior a soltar la palanca registra distancia neta y acumulada, giro residual y monitor de espera. Una espera no confirmada indica que no hubo un segundo válido de espera fija en el tiempo disponible. Se informa inestabilidad si se observa caída, contacto ajeno a los pies o inclinación superior a 15° (umbral de desarrollo del ensayo).

El control centrado se mide también en las ventanas correspondientes a los pulsos. La resta de desplazamientos es descriptiva: cada corrida tiene su propia evolución de estado. La selección entre corridas completas sin contactos ni inclinación excesiva prioriza el número de respuestas sobre los umbrales publicados, el signo de retroceso, el número de sentidos, la media de respuesta firmada dividida por la integral solicitada y el menor salto máximo. La selección usa la misma grabación, por lo que es desarrollo.

| Reactivación | Sentido | Umbral 2 cm / 0,05 rad | Esperas confirmadas tras pulso | Salto máximo total | Inclinación máx. |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0,50 s | 4/5 | 0/5 | 2/5 | 10,47° | 2,76° |
| 0,20 s | 3/5 | 2/5 | 2/5 | 11,19° | 2,83° |
| 0,10 s | 5/5 | 2/5 | 2/5 | 11,21° | 2,71° |

Las tres corridas terminaron 33 s sin caída ni contacto ajeno a pies. La variante de 0,10 s ganó la comparación y pasó el protocolo de 49 s con consignas de 3 s, con 7/7 sentidos y 8/8 esperas. El retroceso corto apenas alcanzó 0,56 mm en el sentido pedido. Los saltos durante los propios pulsos aumentaron, aunque el máximo de toda la grabación aumentó solo un 7,1%. Estos resultados no establecen límites de actuación física.

La corrida centrada se desplazó 8,28 cm en distancia neta durante 30 s, confirmando reposo a los 2,62 s tras activar el GRU. El desplazamiento neto de control durante la primera ventana de retroceso fue +0,95 cm. Las pausas intermedias no confirmaron espera antes de la nueva consigna en ninguna variante y no presentaron inestabilidad observada.

Los archivos `summary.json`, `comparacion-variantes.csv`, `comparacion-pulsos.csv` y los CSV de cada trayectoria se conservan en la salida. La variante 0,50 s reproduce la trayectoria publicada anterior sin diferencias dinámicas. El robot puede permanecer desconectado.
