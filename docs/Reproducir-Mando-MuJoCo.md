# Reproducir un registro del mando en MuJoCo

La entrada es un CSV de shadow con `pc_time_s`, `cmd_vx`, `cmd_vy`, `cmd_yaw`. Los archivos de postura corresponden a las capturas de pie 1 y 2. Se genera la referencia wait-mean únicamente con la primera y se inicializa FixStand con la segunda, usando el protocolo continuo anterior. El robot puede estar desconectado.

```bash
cd ~/go2-rl-deploy
git pull --ff-only
mkdir -p pruebas
.venv-sim/bin/python reproducir_mando.py \
  --calibration "$HOME/transicion_a_de_pie_19700103-121457.csv" \
  --initial "$HOME/transicion_02_19700103-130220.csv" \
  --remote-csv "$HOME/go2_mando_ejes.csv" \
  --out "pruebas/mando-replay-$(date +%Y%m%d-%H%M%S)" --view
```

Quita `--view` para el ensayo sin visor. Los tiempos del mando se llevan al origen de su primera muestra y se remuestrean a 50 Hz tomando la última muestra disponible, sin interpolación. La última decisión ocurre antes del fin del registro; se termina en el siguiente límite de 20 ms. El nuevo CSV `consignas_50hz.csv` conserva la fila de origen de cada decisión. Los pulsos se agrupan por signo de los tres componentes. Ninguno se alarga artificialmente para dar tiempo al controlador.

El ensayo usa los mismos objetivos GRU, mezcla de 0,5 s, criterio de transición a espera y estado físico continuo del experimento FixStand. Las observaciones se obtienen del simulador. Las posiciones, torques e IMU de la grabación del mando no se usan como observaciones de la política.

Por pulso se guarda su duración original y discretizada, magnitud media y máxima de consigna, desplazamiento en el marco inicial de la maniobra, giro neto y dirección. Para un movimiento lineal se verifica el signo y el umbral previo de 2 cm, y para giro se verifica el signo y el umbral de 0,05 rad. El resumen registra también distancia neta, longitud de trayectoria y giro después de soltar el mando hasta la próxima consigna o el final del registro. Una espera confirmada exige un segundo de consigna fija con mezcla terminada sin contactos indebidos y las mismas cotas de rapidez del protocolo anterior. Los intervalos demasiado cortos se conservan y se registran como espera no confirmada.

## Registro de desarrollo

La captura de 30 s contiene cinco impulsos (retroceso, dos laterales y dos giros) separados por intervalos centrados. Los 1.500 ciclos de reproducción coinciden exactamente con la retención a 20 ms y conservan los cinco pulsos. La prueba completa de 33 s terminó sin caída ni contacto ajeno a pies. El retroceso se desplazó 4,3 mm en el sentido contrario; los dos laterales y los dos giros mostraron el signo pedido, con magnitudes muy pequeñas. Ningún pulso superó los umbrales anteriores. La espera se confirmó tras el primer y último pulso. Las pausas intermedias no alcanzaron el criterio antes de la próxima consigna. Esta grabación no incluye avance.

La evidencia pertenece a simulación de desarrollo y no valida teleoperación física. El CSV físico y los archivos de posición originales se mantienen localmente.

[Comparación de tiempos de reactivación espera → GRU](Comparar-Reactivacion-MuJoCo.md).
