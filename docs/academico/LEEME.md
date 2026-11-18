# Proyecto final de robótica avanzada

**Empieza por el [informe PDF](Informe-Proyecto-Final.pdf) y la [presentación editable](Presentacion-Go2.pptx), con el [guion de 15 minutos](Guion-15-min.pdf).** Esta versión reúne pruebas en MuJoCo y la comparación A0/P0 E1–E5. Las métricas recurrentes A2/P0 pertenecen a revisiones internas y a una prueba de integración local.

## Material de entrega

| Archivo | Contenido |
|---|---|
| [Informe PDF](Informe-Proyecto-Final.pdf) | Introducción, metodología, resultados y conclusiones. |
| [Informe LaTeX](Informe-Proyecto-Final.tex), [estilo](Estilo-Go2.tex) y [bibliografía](Referencias.bib) | Fuentes editables con nueve referencias. |
| [Guion oral PDF](Guion-15-min.pdf) y [fuente](Guion-15-min.tex) | Plan de 15 minutos alineado a los puntajes de la exposición. |
| [Flujo experimental](Flujo-Experimental.drawio) | Tres páginas editables para el lazo de control, el diseño experimental y la selección y validación de A2. |
| [Video A0/P0](Demo-A0-U1600-20s.mp4) y [fotograma](Fotograma-A0-U1600.png) | Trote de desarrollo de 20 s en MuJoCo CPU. |
| [Episodios A0](Episodios-A0.csv) y [huellas](Fuentes-de-datos.json) | Aprobación, caída, duración, RMSE y emparejamiento por consigna, escenario y semilla. |
| [Figura por escenario](Resultados-por-escenario.png) y [figura de error de avance](Error-de-avance.png) | Gráficos a partir de los episodios comunes. |
| [Presentación PPTX](Presentacion-Go2.pptx) y [copia PDF](Presentacion-Go2.pdf) | Diez diapositivas con notas de exposición. |
| [Lateral A2/P0](Demo-A2-U2000-Lateral-20s.mp4), [telemetría](Telemetria-A2-U2000.csv) y [huellas](Evidencia-A2-U2000.json) | Demostración de 20 s en MuJoCo CPU. |
| [Último corte verificado](Corte-del-Laboratorio.md) y [desarrollo A2](Desarrollo-A2-Continuacion.csv) | Estado fechado y 50 episodios de desarrollo. |
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

## Mantener al día la entrega

Publica los hitos después de verificar sus resultados y anota la fecha de corte en Corte-del-Laboratorio.md. Actualiza el anexo del informe y las diapositivas con los mismos números. GitHub conserva el historial. En Drive se reemplazan los archivos vigentes manteniendo sus enlaces, y se añaden los recursos nuevos como archivos separados. El salón de presentación puede abrirse sin conexión si se descargan el PPTX y los dos MP4.

El constructor editable de la presentación es Construir-Presentacion.mjs. Usa el paquete @oai/artifact-tool y las imágenes de esta carpeta. El PDF de diapositivas se obtiene exportando el PPTX. El README de la raíz enlaza esta entrega y el panel de simulación.
