import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const directory = path.dirname(fileURLToPath(import.meta.url));
const output = process.argv[2] || path.join(directory, "Presentacion-Go2.pptx");
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const C = { paper:"#F4F7FA", white:"#FFFFFF", navy:"#102335", ink:"#163045",
  quiet:"#435B70", teal:"#087B67", blue:"#16546F", line:"#CCD8E0", light:"#ADE5D4" };
const FONT = "Liberation Sans";
const source = "https://github.com/daca2022/go2-rl-deploy/tree/main/docs/academico";
const drive = "https://drive.google.com/drive/folders/1S8uEebuWrVEXju7h-1b8J_P_9BeeqBDS";

function shape(s, geometry, x, y, w, h, fill="none") {
  return s.shapes.add({geometry,position:{left:x,top:y,width:w,height:h},fill,
    line:{style:"solid",fill:"none",width:0}});
}
function text(s, string, x, y, w, h, px, options={}) {
  const q=shape(s,"textbox",x,y,w,h);
  q.text=string;
  q.text.style={typeface:FONT,fontSize:px,bold:options.bold||false,color:options.color||C.ink,
    alignment:options.align||"left",verticalAlignment:"middle",insets:{left:0,right:0,top:0,bottom:0}};
  return q;
}
function rect(s,x,y,w,h,color) {return shape(s,"rect",x,y,w,h,color);}
function slide(title, subtitle) {
  const s=deck.slides.add();
  s.background.fill=C.paper;
  rect(s,64,44,60,5,C.teal);
  text(s,title,63,68,1150,62,42,{bold:true});
  if(subtitle) text(s,subtitle,65,145,1148,38,23,{color:C.quiet});
  rect(s,65,664,1150,1,C.line);
  text(s,"UNITREE GO2  /  ROBÓTICA AVANZADA",65,673,520,23,15,{color:C.quiet});
  text(s,String(deck.slides.items.length).padStart(2,"0"),1164,673,51,23,15,{align:"right",color:C.quiet});
  return s;
}
function note(s, contents, links=[]) {
  s.speakerNotes.text=contents + (links.length ? "\n\nFuentes\n"+links.join("\n") : "");
}
async function pic(s,name,x,y,w,h,alt) {
  const b=await fs.readFile(path.join(directory,name));
  const blob=b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
  s.images.add({blob,contentType:"image/png",alt,fit:"contain",
    position:{left:x,top:y,width:w,height:h}});
}
function label(s,title,body,x,y,w) {
  text(s,title,x,y,w,39,26,{bold:true,color:C.teal});
  text(s,body,x,y+53,w,108,25);
}

{
  const s=deck.slides.add();s.background.fill=C.navy;
  rect(s,68,91,76,6,C.light);
  text(s,"Proyecto final · Robótica avanzada",66,123,580,39,24,{color:C.light});
  text(s,"Locomoción del\nUnitree Go2",64,196,530,155,63,{bold:true,color:C.white});
  text(s,"Aprendizaje por refuerzo y control PD\nen MuJoCo",67,392,515,78,28,{color:C.white});
  await pic(s,"Fotograma-A2-U2000.png",615,168,590,332,"Go2 simulado durante el desplazamiento lateral A2");
  text(s,"Captura del A2/P0 U2000 en MuJoCo",617,519,590,28,19,{color:C.light});
  note(s,"0:00–0:45. Presentar el objetivo. El proyecto combina generación aprendida y un controlador articular. Las demostraciones de esta exposición corresponden a simulación.",[source,drive]);
}
{
  const s=slide("Qué debe hacer el Go2","Controlar doce articulaciones mientras sigue consignas y mantiene el equilibrio.");
  label(s,"Avance y retroceso","0,30 m/s hacia delante\n−0,20 m/s hacia atrás",65,268,345);
  label(s,"Desplazamiento lateral","0,20 m/s hacia un lado\nsin perder el equilibrio",453,268,350);
  label(s,"Giro","0,30 rad/s alrededor\ndel eje vertical",841,268,365);
  text(s,"Pregunta experimental",65,493,1100,36,27,{bold:true,color:C.teal});
  text(s,"¿Cómo cambian el seguimiento y la estabilidad al modificar la receta de entrenamiento?",65,548,1115,56,28,{bold:true});
  note(s,"0:45–1:30. Distinguir entre consignas de una misma política de locomoción y habilidades diferentes. Plantear la comparación E1–E5 con igual número de transiciones.",[source]);
}
{
  const s=slide("Cómo se genera el movimiento","La política actúa a 50 Hz y MuJoCo integra la dinámica a 200 Hz.");
  const parts=[
    ["Observaciones","47 entradas\nIMU, juntas y consigna"],
    ["Actor PPO","A0 instantáneo\nA1 historial · A2 GRU"],
    ["Control P0","Posición objetivo\nRealimentación PD"],
    ["Go2 simulado","12 articulaciones\nDinámica y contactos"]
  ];
  parts.forEach(([title,body],i)=>{
    const x=66+i*296;
    rect(s,x,252,244,146,C.white);
    rect(s,x,252,244,4,C.teal);
    text(s,title,x+14,276,220,33,25,{bold:true});
    text(s,body,x+14,322,220,57,20);
    if(i<3) text(s,"→",x+250,300,39,47,30,{color:C.teal,align:"center"});
  });
  text(s,"La posición y velocidad de las juntas realimentan el controlador.",65,455,1150,52,25);
  text(s,"PPO actualiza la política con trayectorias simuladas. La GRU conserva un estado entre decisiones.",65,543,1140,65,24,{color:C.quiet});
  note(s,"1:30–4:00. Explicar PD con q deseado y velocidad articular. T0 aplica torque directo en la comparación posterior. La observación base tiene 47 entradas y A1 usa cinco cuadros causales. MuJoCo resuelve contactos y dinámica.",["https://arxiv.org/abs/1707.06347","https://aclanthology.org/D14-1179/",source+"/Flujo-Experimental.drawio"]);
}
{
  const s=slide("E1 y E5 usaron el mismo presupuesto","3.072.000 transiciones, semilla 7 y las mismas cuatro consignas.");
  label(s,"E1 · referencia nominal","Entrenamiento continuo en plano.\nTiempo total de 2 h 12 min.",65,254,526);
  label(s,"E5 · entorno progresivo","PPO por bloques en plano. El entorno\ncambió reinicio y cálculo de despeje.",676,254,528);
  rect(s,592,247,1,183,C.line);
  text(s,"6 h 20 min",64,474,360,75,49,{bold:true,color:C.teal});
  text(s,"duró E5. Unas 4 h fueron revisiones internas con pesos congelados.",429,478,763,65,27);
  note(s,"4:00–5:50. Describir 64 entornos × 24 decisiones × 2.000 actualizaciones. La primera promoción E5 ocurrió al finalizar U2000. Explicar que evaluar con pesos congelados consume pared y no añade muestras de aprendizaje.",[source+"/Informe-Proyecto-Final.pdf",source+"/Episodios-A0.csv"]);
}
{
  const s=slide("Qué cuenta como trote aprobado","En la evaluación se conservan los fallos y se informa cada escenario por separado.");
  label(s,"20 s sin caer","Se verifica la llegada al\nhorizonte de simulación.",65,237,320);
  label(s,"Seguimiento","RMSE lineal ≤ 0,10 m/s.\nLímite angular de 0,15 rad/s.",454,237,338);
  label(s,"Patrón de apoyos","El monitor comprueba el\npatrón de trote registrado.",842,237,340);
  text(s,"7 condiciones y 138 episodios comunes para E1 y E5",65,474,1140,52,32,{bold:true,color:C.teal});
  text(s,"Plano, fricción, empujón, ruido, masa con retardo, terreno rugoso y pendiente.",65,551,1140,42,23);
  note(s,"5:50–7:30. Definir RMSE. Explicar el emparejamiento por consigna, condición y semilla de evaluación. Hubo 140 episodios programados y 138 comunes. Una semilla de entrenamiento limita la generalización.",[source+"/Episodios-A0.csv"]);
}
{
  const s=slide("El Go2 sigue consignas en MuJoCo","Dos reproducciones de desarrollo de 20 s.");
  await pic(s,"Fotograma-A0-U1600.png",66,222,536,301,"Trote de avance del Go2 A0 U1600 en MuJoCo");
  await pic(s,"Fotograma-A2-U2000.png",677,222,536,301,"Desplazamiento lateral del Go2 A2 U2000 en MuJoCo");
  text(s,"A0/P0 U1600 · avance",65,539,536,42,27,{bold:true});
  text(s,"A2/P0 U2000 · lateral",676,539,536,42,27,{bold:true});
  text(s,"Consigna 0,30 m/s · RMSE 0,0723 m/s",65,589,536,33,20,{color:C.quiet});
  text(s,"Consigna 0,20 m/s · media 0,110 m/s",676,589,536,33,20,{color:C.quiet});
  note(s,"7:30–9:30. Reproducir los dos MP4 locales o abrirlos desde Drive. Ambos clips terminaron los 20 s sin caída en sus demostraciones. Señalar que el lateral todavía queda por debajo de la velocidad pedida. Los videos son recursos separados.",[drive,source+"/Demo-A0-U1600-20s.mp4",source+"/Demo-A2-U2000-Lateral-20s.mp4"]);
}
{
  const s=slide("Cada receta destaca en escenarios distintos","Resultados de E1 y E5 sobre los mismos 138 episodios.");
  await pic(s,"Resultados-por-escenario.png",66,209,720,391,"Tasas de aprobación por escenario para E1 y E5");
  text(s,"100/138 · 98/138",825,244,362,69,37,{bold:true,color:C.teal});
  text(s,"E1 tuvo menor error de avance en plano y con masa y retardo.",825,337,355,96,24);
  text(s,"E5 obtuvo 8/18 en terreno rugoso. E1 obtuvo 5/18.",825,451,355,93,24);
  text(s,"Ambos quedaron en 0/20 en pendiente de 5°.",825,557,355,61,23,{color:C.quiet});
  note(s,"9:30–11:10. En los 138 pares hubo 94 dobles aprobados, 34 dobles fallos, 6 aprobados solo por E1 y 4 solo por E5. Los pares de evaluación comparan actores de una sola semilla de entrenamiento. El error mediano de avance en plano fue 0,0608 para E1 y 0,0743 m/s para E5. Bajo masa y retardo quedó en 0,0917 y 0,1032. Los incrementos son parecidos.",[source+"/Episodios-A0.csv",source+"/Resultados-por-escenario.png"]);
}
{
  const s=slide("U2400 conserva el mejor plano observado","Continuación A2/P0 desde U2000. Corte del 18 de noviembre de 2026.");
  const xs=[66,306,640,926];
  const widths=[240,334,286,288];
  const rows=[
    ["Checkpoint","Trote en plano","20 s sin caída en plano","Reto de desarrollo"],
    ["U2400","20 de 20","20 de 20","5 de 5 en +1°"],
    ["U2800","10 de 20","20 de 20","0 de 5 en +5°"],
    ["U3200","15 de 20","20 de 20","1 de 5 en masa +10 %"],
    ["U3600","15 de 20","20 de 20","3 de 5 · retardo 20 ms"],
    ["U4000","15 de 20","20 de 20","2 de 5 · masa y retardo"]
  ];
  rows.forEach((row,i)=>{
    const y=202+54*i; rect(s,66,y,1148,50,i===0?C.navy:C.white);
    row.forEach((value,j)=>text(s,value,xs[j]+13,y+4,widths[j]-24,45,i===0?20:j===3?21:25,
      {bold:i===0||j<2,color:i===0?C.white:C.ink}));
  });
  text(s,"En pendiente emparejada, U4000 terminó 6/6 sin caída y U2400 4/6.",66,537,1120,63,27,{color:C.quiet});
  note(s,"11:10–13:00. Diferenciar pasar el horizonte y aprobar el monitor. Los retos de +1°, +5°, masa +10 % y retardo de 20 ms cambian de condición. U3600 aprobó 3/5 con retardo y completó los cinco horizontes. U4000 completó 25/25 sin caídas y aprobó 2/5 con masa +10 % y 20 ms de retardo. U2400 conserva el único filtro plano completo en cinco revisiones. En 8 pares de desarrollo, U4000 dio mejor estabilidad en pendiente. El filtro común es 0,10 m/s. Esta rama es diferente al entrenamiento A2/P0 original U2800.",[source+"/Desarrollo-A2-Continuacion.csv",source+"/Corte-del-Laboratorio.md"]);
}
{
  const s=slide("Qué verificamos además del trote","Pruebas de ingeniería en MuJoCo CPU.");
  const rows=[
    ["Maestro y alumno","48 etiquetas y 2 actualizaciones del alumno.\nDos episodios de 0,48 s. Evaluación oficial pendiente."],
    ["Handstand","Pose colocada estable 3,155 s. Entrada fallida a los 0,700 s.\nFaltan la entrada y el retorno en un mismo episodio."],
    ["Otras habilidades","Los ensayos de sentarse y pronking terminaron sin caída.\nLos monitores registraron fallo de habilidad en ambos."]
  ];
  rows.forEach(([title,body],i)=>{
    const y=217+i*91;
    text(s,title,65,y,255,64,25,{bold:true,color:C.teal});
    text(s,body,342,y,866,68,24);
  });
  rect(s,65,498,1150,1,C.line);
  text(s,"Campaña con 1 de 6 entrenamientos y 0 validaciones verificadas.",65,516,1140,38,24,{color:C.quiet});
  text(s,"Siguiente hito",65,578,255,36,26,{bold:true,color:C.teal});
  text(s,"U4000 es candidato de desarrollo por estabilidad. La validación formal sigue pendiente.",342,568,865,63,24);
  note(s,"13:00–15:00. La recuperación a U4000 quedó verificada. Los cinco cortes suman 125 episodios de desarrollo. La validación de la matriz sigue pendiente. En el diagnóstico inicial, el maestro realizó una actualización PPO con 48 transiciones y el alumno dos actualizaciones con 48 etiquetas. La evaluación del alumno solo duró dos episodios de 0,48 s. En Handstand, el sostén de 3,155 s comenzó con una pose colocada y la entrada natural falló a los 0,700 s. Sentarse duró 6 s sin sostén válido y pronking 20 s con cero vuelos válidos. Se verificaron 5.200 subpasos entre ambos episodios. Los 12 cambios de entrada conservaron física y GRU del mismo trote y todavía falta entrenar y evaluar cuatro habilidades. La campaña completa y F1–F4 siguen pendientes. Los lanzamientos CUDA corresponden al usuario.",[source+"/Corte-del-Laboratorio.md",source+"/Informe-Proyecto-Final.pdf",drive]);
}
{
  const s=slide("Alumno GRU en terreno irregular","Evaluación reservada en MuJoCo, 20 episodios por actor.");
  text(s,"20/20 por actor, sin caídas ni contactos del cuerpo",68,214,1140,78,41,{bold:true,color:C.teal});
  text(s,"Irregular · error medio de 0,1295 a 0,0857 m/s",68,333,1140,68,31);
  text(s,"Pendiente de +5° · de 0,1312 a 0,1370 m/s",68,411,1140,68,31);
  text(s,"Referencia PPO U4000 frente al alumno entrenado con el maestro U4300.",68,524,1130,75,26);
  note(s,"Resultados reservados de destilación. Reproducir el video de desarrollo de 20 s y distinguirlo de los episodios reservados. La aceptación física sigue pendiente.",[source+"/Alumno-GRU-Episodios.csv",source+"/Demo-Alumno-GRU-Avance.mp4"]);
}
{
  const s=slide("Respuesta a pulsos cortos del mando","Desarrollo en MuJoCo, no evaluación reservada ni prueba física.");
  await pic(s,"Respuesta-Pulsos-GRU.png",65,204,735,357,"Comparación de traslación en tres pulsos cortos");
  text(s,"7/7 maniobras\n8/8 esperas",852,233,335,100,36,{bold:true,color:C.teal});
  text(s,"49 s sin caídas ni contacto corporal",852,350,340,80,26);
  text(s,"Pulsos: 5/5 sentidos; solo 2/5 alcanzan el umbral",852,457,340,88,24);
  text(s,"Mejora parcial: la traslación todavía es inferior a 1 cm.",65,584,1150,55,24,{color:C.quiet});
  note(s,"Anexo de desarrollo. La comparación conserva los cinco pulsos y los pesos. Retroceso de 0,056 a 0,759 cm; derecha de 0,119 a 0,540 cm. Algunos frenados y saltos articulares empeoraron. La aceptación física está pendiente.",[source+"/Pulsos-GRU-Desarrollo.csv",source+"/Pulsos-GRU-Desarrollo.json"]);
}
{
  const s=slide("Referencias y reproducibilidad","Material de consulta para preguntas.");
  const refs=[
    "Todorov, Erez y Tassa (2012) · MuJoCo y dinámica de contactos",
    "Schulman et al. (2017) · Optimización proximal de políticas, PPO",
    "Cho et al. (2014) · Redes recurrentes con compuertas",
    "Rudin et al. (2022) · Locomoción con aprendizaje paralelo y currículo",
    "Engstrom et al. (2020) y Henderson et al. (2018) · Implementación y reproducibilidad"
  ];
  refs.forEach((value,i)=>text(s,value,65,221+i*60,1150,38,25));
  text(s,"Drive y GitHub reúnen el informe, sus fuentes, el diagrama y los datos.",65,565,1140,55,24,{bold:true,color:C.teal});
  note(s,"Diapositiva de respaldo. Recordar que la bibliografía completa, las fuentes LaTeX y los datos siguen disponibles en la carpeta pública.",["https://doi.org/10.1109/IROS.2012.6386109","https://arxiv.org/abs/1707.06347","https://aclanthology.org/D14-1179/","https://proceedings.mlr.press/v164/rudin22a.html","https://arxiv.org/abs/2005.12729","https://arxiv.org/abs/1709.06560",drive,source]);
}

await (await PresentationFile.exportPptx(deck)).save(output);
