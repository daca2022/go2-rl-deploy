# Estado verificado del laboratorio Go2

**Corte del 18 de noviembre de 2026.** La entrega corresponde a simulación en MuJoCo. Las demostraciones y revisiones de desarrollo se mantienen separadas de la validación reservada.

| Evidencia | Resultado al corte |
|---|---|
| Comparación inicial A0 | E1 100/138 y E5 98/138 en episodios comunes, con 3.072.000 transiciones por entrenamiento. |
| Video A0/P0 U1600 | 20 s de trote en avance en MuJoCo CPU. |
| Video A2/P0 U2000 | 20 s de lateral, 1.000 decisiones, 4.000 subpasos y cero caídas diagnósticas. Consigna 0,20 m/s. Velocidad lateral media 0,11021 m/s. RMSE planar 0,09483 m/s. |
| A2 original | Semilla 7, 2.800 actualizaciones completadas en CUDA y 4.300.800 transiciones. |
| Continuación A2 desde U2000 | U2940 de U4000 en el último log observado. Dos de cinco revisiones internas completas. Recibo final pendiente. |
| U2400 de la continuación | 20/20 aprobados en plano y 5/5 en retroceso sobre +1°. |
| U2800 de la continuación | 10/20 aprobados en plano, con 20/20 al horizonte. En +5°, 5/5 al horizonte y 0/5 en el monitor completo de trote. |
| Comparación A0/A1/A2 con P0/T0 | Seis constructores, PPO corto y recarga verificados en CPU. El protocolo empareja 140 episodios por corrida. |
| Reanudación DC | Igualdad de trayectoria, optimizador y estado aleatorio al reanudar una actualización verificada de A1/DC/P0 en CPU. |

Los cortes de pendiente usan distintas inclinaciones. La selección A2 sigue abierta hasta verificar el recibo y revisar los cinco bloques. El CSV de desarrollo contiene los 50 episodios verificados, con su huella de registro. Los números de U2800 en la continuación pertenecen a esa rama y son distintos de los resultados del A2 U2800 original.

El plan maestro conserva 41 de 56 entradas cerradas. Quedan la validación reservada, la comparación de calidad, las cuatro habilidades y la verificación final. Los lanzamientos GPU corresponden al operador.

- [Datos de desarrollo A2](Desarrollo-A2-Continuacion.csv)
- [Informe PDF](Informe-Proyecto-Final.pdf) y [presentación](Presentacion-Go2.pptx)
- [Carpeta pública de Drive](https://drive.google.com/drive/folders/1S8uEebuWrVEXju7h-1b8J_P_9BeeqBDS)
