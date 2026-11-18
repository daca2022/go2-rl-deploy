# Estado verificado del laboratorio Go2

**Corte del 18 de noviembre de 2026.** La entrega corresponde a simulación en MuJoCo. Las demostraciones y revisiones de desarrollo se mantienen separadas de la validación reservada.

| Evidencia | Resultado al corte |
|---|---|
| Comparación inicial A0 | E1 100/138 y E5 98/138 en episodios comunes, con 3.072.000 transiciones por entrenamiento. |
| Video A0/P0 U1600 | 20 s de trote en avance en MuJoCo CPU. |
| Video A2/P0 U2000 | 20 s de lateral, 1.000 decisiones, 4.000 subpasos y cero caídas diagnósticas. Consigna 0,20 m/s. Velocidad lateral media 0,11021 m/s. RMSE planar 0,09483 m/s. |
| A2 original | Semilla 7, 2.800 actualizaciones completadas en CUDA y 4.300.800 transiciones. |
| Continuación A2 desde U2000 | Tres de cinco revisiones internas completas hasta U3200 de U4000. Recibo final pendiente. |
| U2400 de la continuación | 20/20 aprobados en plano y 5/5 en retroceso sobre +1°. |
| U2800 de la continuación | 10/20 aprobados en plano, con 20/20 al horizonte. En +5°, 5/5 al horizonte y 0/5 en el monitor completo de trote. |
| U3200 de la continuación | 15/20 aprobados y 20/20 al horizonte en plano. El lateral quedó en 0/5 con RMSE de 0,12083 m/s. Con 10 % más de masa, 1/5 aprobados y 5/5 al horizonte. |
| Comparación A0/A1/A2 con P0/T0 | Seis constructores, PPO corto y recarga verificados en CPU. El protocolo empareja 140 episodios por corrida. |
| Reanudación DC | Igualdad de trayectoria, optimizador y estado aleatorio al reanudar una actualización verificada de A1/DC/P0 en CPU. |

Los tres cortes usan el mismo filtro nominal de 0,10 m/s. Los retos de cada corte difieren en dificultad y condición. La selección A2 sigue abierta hasta verificar el recibo y revisar los cinco bloques. El CSV de desarrollo contiene los 75 episodios verificados, con su huella de registro. Los números de U2800 en la continuación pertenecen a esa rama y son distintos de los resultados del A2 U2800 original.

El plan maestro conserva 41 de 56 entradas cerradas. Quedan la validación reservada, la comparación de calidad, las cuatro habilidades y la verificación final. Los lanzamientos GPU corresponden al operador.

**Lectura formal de campaña.** El recibo del entrenamiento original A2/P0 verificó 31.526,11 s de pared total, incluidas las revisiones internas. El pico observado fue de 1.119.055.235 B de disco y 2.238.709.760 B de VRAM. La rama de continuación se registra aparte. El borrador de consulta local del panel se verificó en Chrome con ese recibo.

**Terreno irregular.** Se verificó en CPU la agenda de 120 cruces de validación y 120 de test por política, con semillas separadas. En las tres trazas de ingeniería de U1600, el robot salió del corredor antes de cruzarlo, sin caída ni contacto de tronco. Los cruces reservados siguen pendientes.

- [Tabla de seis celdas](Campana-Progresiva-Celdas.csv) y [costes desde el recibo](Campana-Progresiva-Costes.csv)
- [Datos de desarrollo A2](Desarrollo-A2-Continuacion.csv)
- [Informe PDF](Informe-Proyecto-Final.pdf) y [presentación](Presentacion-Go2.pptx)
- [Carpeta pública de Drive](https://drive.google.com/drive/folders/1S8uEebuWrVEXju7h-1b8J_P_9BeeqBDS)
