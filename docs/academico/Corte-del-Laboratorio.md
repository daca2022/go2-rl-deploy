# Estado verificado del laboratorio Go2

**Corte del 18 de noviembre de 2026.** La entrega corresponde a simulación en MuJoCo. Las demostraciones y revisiones de desarrollo se mantienen separadas de la validación reservada.

| Evidencia | Resultado al corte |
|---|---|
| Comparación inicial A0 | E1 100/138 y E5 98/138 en episodios comunes, con 3.072.000 transiciones por entrenamiento. |
| Video A0/P0 U1600 | 20 s de trote en avance en MuJoCo CPU. |
| Video A2/P0 U2000 | 20 s de lateral, 1.000 decisiones, 4.000 subpasos y cero caídas diagnósticas. Consigna 0,20 m/s. Velocidad lateral media 0,11021 m/s. RMSE planar 0,09483 m/s. |
| A2 original | Semilla 7, 2.800 actualizaciones completadas en CUDA y 4.300.800 transiciones. |
| Continuación A2 desde U2000 | Cinco revisiones completas. La recuperación desde U3900 terminó en U4000 con recibo verificado y 125 episodios de desarrollo acumulados. |
| U2400 de la continuación | 20/20 aprobados en plano y 5/5 en retroceso sobre +1°. |
| U2800 de la continuación | 10/20 aprobados en plano, con 20/20 al horizonte. En +5°, 5/5 al horizonte y 0/5 en el monitor completo de trote. |
| U3200 de la continuación | 15/20 aprobados y 20/20 al horizonte en plano. El lateral quedó en 0/5 con RMSE de 0,12083 m/s. Con 10 % más de masa, 1/5 aprobados y 5/5 al horizonte. |
| U3600 de la continuación | 15/20 aprobados y 20/20 al horizonte en plano. Avance con RMSE de 0,07068 m/s. Lateral con 0,12059 m/s y 0/5. Con retardo de 20 ms, 3/5 aprobados y 5/5 al horizonte. |
| U4000 de la recuperación | 15/20 aprobados y 20/20 al horizonte en plano. Lateral 0/5 con RMSE de 0,11120 m/s. Con masa +10 % y retardo de 20 ms, 2/5 aprobados y 5/5 al horizonte. |
| Comparación A0/A1/A2 con P0/T0 | Seis constructores, PPO corto y recarga verificados en CPU. El protocolo empareja 140 episodios por corrida. |
| Reanudación DC | Igualdad de trayectoria, optimizador y estado aleatorio al reanudar una actualización verificada de A1/DC/P0 en CPU. |

Los cinco cortes usan el mismo filtro nominal de 0,10 m/s. Los retos de cada corte difieren en dificultad y condición. U2400 conserva el único filtro nominal completo aprobado. En 8 pares de desarrollo (16 episodios), U4000 completó 6/6 sin caída y aprobó 3/6 en pendiente; U2400 completó 4/6 y aprobó 2/6. Con masa y retardo ambos completaron 2/2; U4000 aprobó 1/2 y U2400 0/2. U4000 queda como candidato de desarrollo por estabilidad. U2400 conserva el filtro nominal completo. La selección formal sigue pendiente. El CSV contiene 100 episodios verificados de la corrida original y 25 nuevos de la recuperación. El intento interrumpido de U4000 dejó 17 episodios parciales que se excluyeron. El [resumen de evidencia](Evidencia-Recuperacion-A2.json) fija las huellas y los costes. Los números de U2800 en la continuación pertenecen a esa rama y son distintos de los resultados del A2 U2800 original.

El plan maestro conserva 42 de 56 entradas cerradas. Quedan la validación reservada, la comparación de calidad, las cuatro habilidades y la verificación final. Los lanzamientos GPU corresponden al operador.

**Lectura formal de campaña.** El recibo del entrenamiento original A2/P0 verificó 31.526,11 s de pared total, incluidas las revisiones internas. El pico observado fue de 1.119.055.235 B de disco y 2.238.709.760 B de VRAM. La rama de continuación se registra aparte. El borrador de consulta local del panel se verificó en Chrome con ese recibo.

**Terreno irregular.** Se verificó en CPU la agenda de 120 cruces de validación y 120 de test por política, con semillas separadas. En las tres trazas de ingeniería de U1600, el robot salió del corredor antes de cruzarlo, sin caída ni contacto de tronco. Los cruces reservados siguen pendientes.

**Integración nominal de PPO y GRU.** Un diagnóstico CPU inicializado desde A2/P0 U2400 llevó tres de cuatro mundos a 20 s naturales. Verificó el bootstrap con observación terminal y el reinicio selectivo de la GRU. La validación reservada sigue pendiente.

**Diagnósticos CPU añadidos al corte.** El maestro privilegiado completó una actualización PPO de 48 transiciones. El alumno usó 48 etiquetas y completó dos actualizaciones de destilación. Sus dos episodios diagnósticos duraron 0,48 s cada uno. La recolección oficial y la evaluación reservada de 20 s siguen pendientes.

En Handstand, una pose colocada sostuvo el apoyo delantero durante 3,155 s. La entrada desde cuatro apoyos falló a los 0,700 s por contacto de las pantorrillas traseras. Un perfil posterior trasladó el 100 % de la carga medida en los pies a las delanteras durante 0,100 s, con 14,7 mm de despeje trasero, y terminó por contacto delantero a los 1,815 s. Quedan por demostrar entrada, sostén y retorno en un mismo episodio.

Los evaluadores de sentarse y pronking conservaron 5.200 subpasos reproducibles en dos episodios nativos con el actor de trote. Sentarse llegó a 6 s sin lograr el sostén y pronking llegó a 20 s con cero vuelos válidos. Los dos monitores registraron fallo de habilidad. Las políticas específicas y los ensayos formales quedan pendientes.

La prueba de transiciones conservó la continuidad de la física y de la GRU en 12 cambios entre entradas de condición. Todos ejecutaron el mismo actor de trote. La política entrenada para cuatro habilidades y sus transiciones siguen pendientes.

El informe de campaña del panel conserva una instantánea verificada del entrenamiento original A2/P0, con una de seis celdas entrenada y cero validaciones verificadas. El recibo de recuperación registra 100 actualizaciones y 153.600 transiciones nuevas, con 1 h 08 min de pared. Sigue pendiente la validación reservada de 140 episodios.

- [Tabla de seis celdas](Campana-Progresiva-Celdas.csv) y [costes desde el recibo](Campana-Progresiva-Costes.csv)
- [Datos de desarrollo A2](Desarrollo-A2-Continuacion.csv)
- [Informe PDF](Informe-Proyecto-Final.pdf) y [presentación](Presentacion-Go2.pptx)
- [Carpeta pública de Drive](https://drive.google.com/drive/folders/1S8uEebuWrVEXju7h-1b8J_P_9BeeqBDS)

[Datos emparejados](Comparacion-U2400-U4000.csv) · [Evidencia](Evidencia-Comparacion-A2.json) · [Video en pendiente](Demo-U2400-U4000-Pendiente.mp4).
