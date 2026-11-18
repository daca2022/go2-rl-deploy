# Proyecto final de robótica avanzada

**Empieza por el [informe PDF](Informe-Proyecto-Final.pdf) y el [guion de 15 minutos](Guion-15-min.pdf).** Esta versión reúne pruebas en MuJoCo y la comparación A0/P0 E1–E5. Las métricas recurrentes A2/P0 pertenecen a revisiones internas y a una prueba de integración local.

## Material de entrega

| Archivo | Contenido |
|---|---|
| [Informe PDF](Informe-Proyecto-Final.pdf) | Introducción, metodología, resultados y conclusiones. |
| [Informe LaTeX](Informe-Proyecto-Final.tex), [estilo](Estilo-Go2.tex) y [bibliografía](Referencias.bib) | Fuentes editables con nueve referencias. |
| [Guion oral PDF](Guion-15-min.pdf) y [fuente](Guion-15-min.tex) | Plan de 15 minutos alineado a los puntajes de la exposición. |
| [Flujo experimental](Flujo-Experimental.drawio) | Dos páginas editables para control, entrenamiento y evaluación. |
| [Video A0/P0](Demo-A0-U1600-20s.mp4) y [fotograma](Fotograma-A0-U1600.png) | Trote de desarrollo de 20 s en MuJoCo CPU. |
| [Episodios A0](Episodios-A0.csv) y [huellas](Fuentes-de-datos.json) | Aprobación, caída, duración, RMSE y emparejamiento por consigna, escenario y semilla. |
| [Figura por escenario](Resultados-por-escenario.png) y [figura de error de avance](Error-de-avance.png) | Gráficos a partir de los episodios comunes. |
| [Resultados A2 por DDS](../Prueba-A2-DDS.json) | Cuatro ensayos de 20 s del actor exportado en MuJoCo. |

Las 278 filas corresponden a 138 registros de E1 y 140 de E5. Usa la columna in_matched_subset con valor 1 para comparar los 138 pares. La columna pass corresponde al monitor de trote, fall a caída y duration_s al tiempo simulado hasta el final registrado. Las huellas completas de realización difieren por corrida. La comparación conserva la identidad de emparejamiento y las huellas de los seis modelos compilados de evaluación.

## Regenerar

En esta carpeta, con TeX Live y Matplotlib disponibles:

~~~bash
python3 Figuras.py
latexmk -pdf Informe-Proyecto-Final.tex
latexmk -pdf Guion-15-min.tex
~~~

Abre el archivo Draw.io en [diagrams.net](https://app.diagrams.net/) mediante **Archivo → Abrir desde → Dispositivo**. El [repositorio público](https://github.com/daca2022/go2-rl-deploy) incluye el panel y la guía para una demostración en vivo con A2/P0.
