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
  note(s,"5:50–7:30. Definir RMSE. Explicar el emparejamiento por consigna, condición y semilla de evaluación. Hubo 140 escenarios programados y 138 comunes. Una semilla de entrenamiento limita la generalización.",[source+"/Episodios-A0.csv"]);
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
  text(s,"100 frente a 98",825,244,362,69,40,{bold:true,color:C.teal});
  text(s,"E1 tuvo menor error de avance en plano y con masa y retardo.",825,337,355,96,24);
  text(s,"E5 obtuvo 8/18 en terreno rugoso. E1 obtuvo 5/18.",825,451,355,93,24);
  text(s,"Ambos quedaron en 0/20 en pendiente de 5°.",825,557,355,61,23,{color:C.quiet});
  note(s,"9:30–11:10. Mostrar ventaja local, no superioridad universal. El error mediano de avance en plano fue 0,0608 para E1 y 0,0743 m/s para E5. Bajo masa y retardo quedó en 0,0917 y 0,1032. Los incrementos son parecidos.",[source+"/Episodios-A0.csv",source+"/Resultados-por-escenario.png"]);
}
{
  const s=slide("U2400 conserva el mejor plano observado","Continuación A2/P0 desde U2000. Corte del 18 de noviembre de 2026.");
  const xs=[66,306,640,926];
  const widths=[240,334,286,288];
  const rows=[
    ["Checkpoint","Trote en plano","20 s sin caída en plano","Reto de desarrollo"],
    ["U2400","20 de 20","20 de 20","5 de 5 en +1°"],
    ["U2800","10 de 20","20 de 20","0 de 5 en +5°"],
    ["U3200","15 de 20","20 de 20","1 de 5 en masa +10 %"]
  ];
  rows.forEach((row,i)=>{
    const y=220+68*i; rect(s,66,y,1148,63,i===0?C.navy:C.white);
    row.forEach((value,j)=>text(s,value,xs[j]+13,y+10,widths[j]-24,50,i===0?20:26,
      {bold:i===0||j<2,color:i===0?C.white:C.ink}));
  });
  text(s,"U3200 recuperó el avance. El lateral registró 0,121 m/s de RMSE con límite de 0,10.",66,537,1120,63,27,{color:C.quiet});
  note(s,"11:10–13:00. Diferenciar pasar el horizonte y aprobar el monitor. Los retos de +1°, +5° y masa +10 % cambian de condición. U2400 conserva el mejor plano en tres revisiones completas. Dejarlo como candidato provisional. El filtro común es 0,10 m/s. Esta rama es diferente al entrenamiento A2/P0 original U2800.",[source+"/Desarrollo-A2-Continuacion.csv",source+"/Corte-del-Laboratorio.md"]);
}
{
  const s=slide("Qué queda demostrado","Locomoción en simulación y una campaña comparativa preparada.");
  label(s,"Evidencia disponible","Videos A0 y A2, datos por episodio y\nmediciones de seguimiento reproducibles.",65,224,535);
  label(s,"Campaña de seis combinaciones","1 entrenamiento CUDA verificado.\n140 episodios de validación por celda.",664,224,543);
  rect(s,65,476,1150,1,C.line);
  text(s,"Siguiente hito",65,510,300,39,28,{bold:true,color:C.teal});
  text(s,"Completar las revisiones de la continuación y elegir el checkpoint para su validación reservada.",355,496,832,85,26);
  note(s,"13:00–15:00. Cerrar con lo que funciona y lo que queda abierto. La campaña completa, las cuatro habilidades finales y las auditorías F1–F4 siguen pendientes. Los lanzamientos CUDA corresponden al usuario.",[source+"/Corte-del-Laboratorio.md",drive]);
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
