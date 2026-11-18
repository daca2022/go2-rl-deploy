# Rúbrica del proyecto final de robótica avanzada

El proyecto demuestra locomoción de un cuadrúpedo en MuJoCo. Una política entrenada con PPO genera consignas de posición articular y un controlador PD sigue esas consignas. El material de exposición muestra dos movimientos verificados y analiza cómo cambia el resultado al modificar el entrenamiento.

## Informe escrito · 10 puntos

| Criterio | Puntos | Dónde verlo |
|---|---:|---|
| Introducción | 1 | Sección 1. Objetivo de locomoción y pregunta sobre la receta de entrenamiento. |
| Metodología | 4 | Sección 2. Lazo de control, PPO, GRU, presupuesto de aprendizaje y episodios emparejados. [Diagrama editable](Flujo-Experimental.drawio). |
| Resultados | 4 | Sección 3 y anexo. Trote por escenario, error de avance, caídas y demostración del actor GRU. [Resultados por escenario](Resultados-por-escenario.png) · [Error de avance](Error-de-avance.png) · [Episodios](Episodios-A0.csv). |
| Conclusiones | 1 | Sección 4. Alcance del resultado y propuesta para aislar un cambio de entrenamiento. |

[Informe PDF](Informe-Proyecto-Final.pdf) · [Fuente LaTeX](Informe-Proyecto-Final.tex) · [Bibliografía](Referencias.bib)

## Exposición oral · 10 puntos y 15 minutos

| Criterio | Puntos | Tiempo | Material |
|---|---:|---|---|
| Introducción | 1 | 0:00–1:30 | Diapositivas 1–2. Objetivo y consignas. |
| Marco teórico | 2 | 1:30–4:00 | Diapositiva 3. MuJoCo, PPO, GRU y control PD. |
| Metodología | 3 | 4:00–7:30 | Diapositivas 4–5. Recetas, transiciones y monitor de trote. |
| Resultados | 3 | 7:30–13:00 | Diapositivas 6–8. Videos, figuras e interpretación. |
| Conclusiones | 1 | 13:00–15:00 | Diapositiva 9. Hallazgos y pruebas pendientes. |

La diapositiva 10 reúne referencias para las preguntas. Para mostrar el funcionamiento, abre el [trote A0](Demo-A0-U1600-20s.mp4) y el [lateral A2](Demo-A2-U2000-Lateral-20s.mp4). Cada clip dura 20 s simulados. El [guion PDF](Guion-15-min.pdf) incluye la secuencia y la opción de demostración en vivo.

[PowerPoint editable](Presentacion-Go2.pptx) · [Diapositivas PDF](Presentacion-Go2.pdf)

## Qué muestran los datos

De 138 pares de evaluación, ambos actores aprobaron 94 y fallaron 34. E1 aprobó seis casos que E5 falló y E5 aprobó cuatro que E1 falló. Con masa y retardo, E1 conservó su margen en velocidad de avance. En terreno rugoso, E5 consiguió más aprobados. La comparación controla las transiciones y conserva una sola semilla de entrenamiento. La fecha, el alcance y las validaciones pendientes están en el [corte del laboratorio](Corte-del-Laboratorio.md).
