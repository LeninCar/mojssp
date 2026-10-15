"""Build the Spanish meeting dossier from audited, separated offline tables."""
from pathlib import Path
import json,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];T=O/'tables'
def read(n):return pd.read_csv(T/(n+'.csv'))
def table(d,cols=None,digits=6):
 if cols is not None:d=d[cols]
 def fmt(v):
  if pd.isna(v):return 'No disponible'
  if isinstance(v,(float,np.floating)):return f'{v:.{digits}f}'
  return str(v).replace('|','/').replace('\n',' ')
 return '\n'+'| '+' | '.join(d.columns)+' |\n| '+' | '.join(['---']*len(d.columns))+' |\n'+'\n'.join('| '+' | '.join(fmt(v) for v in r)+' |' for r in d.itertuples(index=False,name=None))+'\n'
def link(n):return f'[{n}](tables/{n}.csv)'
figmeta=json.loads((O/'figures/figure_manifest.json').read_text(encoding='utf-8'))
FIG={f['id']:f for f in figmeta}
def fig(n):
 f=FIG[n];return '\n!['+f['title']+']('+f['png']+')\n\n**Figura '+n[:2]+'. '+f['title']+'.** '+f['design']+'. '+f['explanation']+' Fuente: ['+f['source']+']('+f['source']+').\n'
LABEL={'moead':'MOEA/D','nsga2':'NSGA-II','spea2':'SPEA2','uniform':'Uniforme','adaptive':'SW-UCB original','scaled':'UCB escalado','guidance':'Padre externo con replay','combined':'Combinado'}
inv=pd.read_csv(O/'05_inventario_instancias.csv');camp=read('campaign_inventory');su=read('recent_summary');pa=read('recent_paired_statistics');best=read('best_algorithm_by_instance');bs=read('recent_base_means');hc=read('historical_summary');profile=read('profile_relative_effects');alloc=read('recent_allocations');comp=read('recent_complementarity');un=read('historical_standalone_union');audit=json.loads((O/'evidence/analysis_audit.json').read_text());cross=json.loads((O/'evidence/cross_campaign_audit.json').read_text());threshold=read('threshold_baseline_final_hv');stale=read('stagnation');ranges=read('objective_ranges');cor=read('exploratory_feature_correlations')
means=su[su.split=='confirmation'].pivot(index='method',columns='metric',values='mean').reset_index();means['method']=means.method.map(LABEL);means=means.rename(columns={'method':'Método','hv':'HV','auc_hv':'AUC-HV','seconds':'Tiempo (s)','unique_vectors':'Vectores únicos','genetic_diversity':'Diversidad genética'})
maincols=['Método','HV','AUC-HV','Tiempo (s)','Vectores únicos','Diversidad genética']
main_table=table(means,maincols)
primary=pa[(pa.split=='confirmation')&(pa.metric=='hv')&(pa.control=='adaptive')&pa.treatment.isin(['scaled','guidance'])]
primary_table=table(primary,['treatment','n_bases','mean_delta','ci_low','ci_high','p_signflip','p_holm_confirmatory_hv','wins','losses','cohen_dz'])
size_df=read('algorithm_by_size');size_confirm=size_df[size_df.campaign=='loop_confirmation'].pivot(index=['size','n_base_clusters'],columns='method',values='mean_hv').reset_index();size_confirm['Mayor media']=size_confirm[['MOEA/D','NSGA-II','SPEA2']].idxmax(axis=1)
size_table=table(size_confirm)
winner=best[best.campaign=='loop_confirmation'][['instance','operations','n_seeds','MOEA/D','NSGA-II','SPEA2','winner']]
versions=pd.DataFrame([
 ['Histórico NSGA-II/MOPSO/NSGA-II+LS','SW-UCB y uniforme; brazos anteriores','Unión pasiva; búsqueda local sólo dentro de su brazo','500/1000 FE; campañas F8','Antecedente; no mezclar con los tres brazos actuales'],
 ['MOEA/D, NSGA-II, SPEA2 individuales','Un brazo usa todo B','Sin intercambio','1000, 3000, 5000; reciente 3000','Controles vigentes'],
 ['Uniforme RR','Bloques cíclicos de 50 FE','Archivo global como salida','Fase 2 y reciente','Control de fragmentación y agregación'],
 ['SW-UCB original','Media ΔHV + bono; W=10,c=.07','Archivo global mide recompensa; sin padre externo','Fase 2, PH y reciente','Línea base conservada'],
 ['UCB1 acumulativo','Media de todas las recompensas + bono','Sin transferencia genética','PH: 5000 FE, 10 bases × 3 semillas','Control de olvido'],
 ['UCB1 + Page-Hinkley C5','Alarma reinicia crédito; δ=.0005, λ=.020','Poblaciones y archivo se conservan','270 calibración + 90 comparación, 5000 FE','No adoptado; sin ventaja corregida'],
 ['UCB escalado','Media ΔHV / máximo reciente + mismo bono','Sin cooperación genética','6 desarrollo y 8 confirmación, 3000 FE','Mejora reproducible frente a SW-UCB'],
 ['Padre externo con replay','Copia exactamente la asignación del control SW-UCB','Un padre extranjero cada 10 cruces elegibles','6 desarrollo y 8 confirmación, 3000 FE tratamiento','Evidencia condicional; coste del control adicional'],
 ['Escalado + padre externo','Decisiones online con crédito escalado','Mismo mecanismo de padre externo','Sólo 6 desarrollo × 3 semillas, 3000 FE','No adoptado; sin ganancia adicional clara'],
 ['SW-UCB c=.01/.03 (P5 paralelo)','Reducir el bono sin escalar crédito','Unión pasiva','2 bases × una semilla; 1000 FE','Sensibilidad exploratoria; ver apéndice 32'],
 ['Inyección acotada P6/P7 paralela','SW-UCB c=.01 y secuencia fija','Hasta 2 incumbentes evaluados por bloque desde índice 6','P6: 2 bases × una semilla; P7 parcial 1000 FE','Distinta de padre externo; corte externo separado']
],columns=['Versión','Selección / asignación','Información compartida','Evidencia','Estado'])
versions.to_csv(T/'portfolio_versions.csv',index=False,encoding='utf-8-sig')
vtable=table(versions)
source_notes="""Los enlaces a tablas remiten a transformaciones reproducibles. Cada fila conserva campaña y fuente cuando corresponde. La relación completa de rutas, tamaños y SHA-256 originales está en [preservation_before.json](evidence/preservation_before.json). No se han ejecutado nuevas optimizaciones. Las inferencias son internas al generador y a las bases observadas; el test final permanece reservado."""
docs={}
def put(n,title,text):docs[n]='# '+title+'\n\n'+text.strip()+'\n'

put('01_evolucion_investigacion.md','Evolución técnica y experimental',f"""
La investigación pasó de un portafolio con NSGA-II, MOPSO y NSGA-II con búsqueda local a un portafolio de MOEA/D, NSGA-II y SPEA2. Esa transición cambia los brazos y limita cualquier comparación directa de campañas F8 con las actuales. La [historia Git](evidence/git_history.txt) distingue implementación, resultados y cierre: MOEA/D `4e596e8`, SPEA2 `7d97f02`, integración de tres brazos `473908a`, scripts de Fase 2 `335b98e`, cierre `ea044c0` y observabilidad `1d695f3`.

## Secuencia reconstruida

1. **Antecedentes F8:** experimentos de parámetros, MOPSO y búsqueda local. Sus resultados diagnostican otra composición del portafolio; no prueban la eficacia de los tres brazos actuales.
2. **Benchmark técnico:** 8 bases, una semilla, cinco individuales, 1000 FE. Sirve para comprobación técnica y costes, con incertidumbre estocástica insuficiente.
3. **Complementariedad Fase 1:** 40 variantes de desarrollo = 8 bases × 5 perfiles; 5 semillas; 600 corridas de 1000 FE. Compara algoritmos completos y uniones cuyo coste es 3B. Las variantes no elevan la muestra independiente a 40.
4. **Fase 2:** piloto de 1000 FE y 150 trayectorias de 5000 FE con cortes de 1000/3000/5000. El piloto y el primer corte tienen idénticos 150 valores de HV: no son dos validaciones independientes de calidad.
5. **Page-Hinkley:** 9 configuraciones, 270 corridas; comparación de UCB1, PH C5 y SW-UCB, 90 corridas. Las 30 filas PH C5 coinciden con calibración. No hubo confirmación en nuevas bases. Conservar SW-UCB por parsimonia no equivale a probar su superioridad estadística.
6. **Auditoría Pareto y procedencia:** se detectó sobreestimación de la contribución leave-one-out histórica; se conserva el resultado heredado y se publica el canónico. Se añadió observabilidad no invasiva. La procedencia no es ascendencia genética.
7. **Campaña del 15 de octubre:** 312 corridas nuevas de 3000 FE; tres iteraciones aisladas: padre externo, escalado del crédito y combinación. Desarrollo: 6 bases × 3 semillas × 8 métodos. Confirmación interna: 8 bases × 3 semillas × 7 métodos. Sólo escalado y padre externo avanzaron a confirmación.

## Todas las versiones
{vtable}
## Qué cambió en la interpretación

El escalado mejora SW-UCB original en las ocho bases de confirmación, pero sigue debajo de MOEA/D en promedio. La cooperación tiene una señal favorable bajo asignación controlada; no constituye aún una política autónoma que incluya el coste de obtener esa asignación. Combinarla con escalado no produjo una ganancia adicional reproducible en desarrollo. El cierre actual es una mejora de un portafolio limitado, sin victoria general sobre sus componentes.

Fuentes: {link('campaign_inventory')}, {link('historical_summary')}, {link('recent_paired_statistics')}, [auditoría de dependencias](evidence/cross_campaign_audit.json). {source_notes}
""")

architecture=r"""
## Modelo y representación

Cada operación tiene máquina fija, precedencia dentro del trabajo, release y varios modos (duración, energía). El genotipo incluye una secuencia de trabajos con repeticiones y un vector de modos por operación canónica. POX conserva las multiplicidades. El decodificador serial usa:

\[
S_{jk}=\max(C_{j,k-1},a_{M_{jk}},r_{jk}),\qquad C_{jk}=S_{jk}+p_{jkv}.
\]

Esto conserva precedencias, disponibilidad de máquina, releases y ejecución no interrumpida. No hay asignación flexible de máquina en estos datos JSP2. Se minimizan \(C_{max}=\max_j C_j\), \(T=\sum_j\max(0,C_j-d_j)\) y \(E=\sum_o e_{o,v_o}\). El due date del trabajo procede de la última operación en orden tecnológico, no del máximo due date de la fila. La energía implementada suma energías de procesamiento por modo; no se añade un modelo nuevo de energía ociosa. Los archivos no declaran unidades físicas homogéneas: se usan unidades de tiempo y energía de la instancia, sin afirmar kWh.

```mermaid
flowchart TD
 I[Instancia y normalizador fijo] --> M[MOEA/D: subproblemas y vecinos]
 I --> N[NSGA-II: ranking y crowding]
 I --> S[SPEA2: fuerza y densidad]
 B[Presupuesto total FE] --> O[Orquestador: elegir y ejecutar bloque]
 U[Selector RR / SW-UCB / escalado] --> O
 O --> M
 O --> N
 O --> S
 M --> A[Archivos locales de soluciones evaluadas]
 N --> A
 S --> A
 A --> G[Archivo Pareto global]
 G --> H[HV con referencia fija]
 H --> R[Recompensa no negativa delta HV]
 R --> U
 G -. sólo variante cooperativa: donante congelado por bloque .-> P[Segundo padre externo]
 P -. cada diez cruces elegibles .-> O
```

## Flujo de un bloque y control de FE

```mermaid
flowchart LR
 A[FE remanentes] --> B[Elegir brazo y limitar bloque]
 B --> C[Opcional: preparar donante extranjero]
 C --> D[Reanudar estado del brazo]
 D --> E[Crear hijo factible, decodificar, evaluar]
 E --> F[Contabilizar una FE por evaluación]
 F --> G[Actualizar selección nativa y archivo local]
 G --> H[Unir archivo global y calcular HV]
 H --> J[Registrar delta HV y actualizar selector]
 J --> K[Siguiente bloque o detener]
```

Las poblaciones no se reinicializan al cambiar de brazo. La inicialización consume FE. En la campaña reciente hay tres bloques neutrales de 50 FE y después una prueba adaptativa de un bloque por brazo; warmup no aprende recompensas en el selector. El archivo global informa la selección mediante HV incluso sin transferencia genética. Esa comunicación de crédito no implica que los algoritmos lean sus genotipos.

## Cinco mecanismos diferentes

| Mecanismo | Qué recibe cada algoritmo | Qué cambia |
|---|---|---|
| Unión pasiva | Nada del otro brazo | Sólo salida Pareto global |
| Archivo compartido como indicador | El selector observa HV global | Crédito y asignación |
| Selección adaptativa | Más o menos bloques de ejecución | Profundidad de búsqueda |
| Padre externo | Un genotipo del archivo global | Variación genética |
| PH | Ningún genotipo nuevo | Memoria del selector tras alarma |

Un archivo común no prueba cooperación genética. La unión de individuales usa 3B FE; un portafolio real reparte B FE. Una solución producida tras cruce externo se acredita al receptor que la evalúa. La primera observación no identifica todos sus ancestros.
"""
put('02_arquitectura_portafolio.md','Arquitectura y definiciones del problema',architecture+'\n\nFuentes de implementación: `src/mojssp/io.py`, `decoder.py`, `evaluator.py`, `portfolio.py`, `orchestrator.py`, `cooperation.py`; copias y hashes en [evidencia](evidence/preservation_before.json).')

formula=r"""
## Fórmulas auditadas

Se normaliza cada objetivo con cotas analíticas de **esa instancia**, fijas durante una corrida:
\[
z_k=(f_k-L_k)/(U_k-L_k),\quad R=(1.1,1.1,1.1).
\]
Si la cota coincide se asigna cero, comprobando primero la pertenencia al intervalo. No se permite recortar violaciones reales para mejorar el indicador. La cota inferior de Cmax es \(\max_{j,k}(r_{jk}+\sum_{h\ge k}\min_v p_{jhv})\); la superior es \(\max r+\sum_o\max_v p_{ov}\). Energía usa suma de mínimos/máximos; tardanza inferior cero y superior \(\sum_j\max(0,U_C-d_j)\). Las cotas pueden ser muy conservadoras. El HV máximo teórico de la caja normalizada y referencia es 1.331: **HV > 1 es válido**.

\[
HV(A)=\operatorname{vol}\left(\bigcup_{z\in ND(A)}[z_1,R_1]\times[z_2,R_2]\times[z_3,R_3]\right),\quad
r_t=\max(0,HV(A_t)-HV(A_{t-1})).
\]

La recompensa usada por UCB es ΔHV por bloque, no ΔHV/FE. El diagnóstico puede dividir por 50 FE, pero no cambia la señal registrada. Para SW-UCB original:
\[
U_i(t)=\bar r_{i,W}+c\sqrt{\log(\min(t,W))/n_{i,W}},\quad W=10,\ c=0.07.
\]
La ventana contiene las últimas W observaciones **globales**, no W observaciones por brazo. Un brazo ausente tiene UCB infinito; empates usan RNG sembrado. Tras warmup se garantiza un probe por brazo. UCB1 usa media y recuento acumulativos, con log(t) en lugar de la ventana. Uniforme RR ignora recompensas y rota determinísticamente.

En escalado se conservan recompensas crudas y se calcula al decidir:
\[
s_t=\max_{(i,r)\in W}|r|\quad(1\text{ si todos son cero}),\qquad
U_i^{esc}=\bar r_{i,W}/s_t+c\sqrt{\log(\min(t,W))/n_{i,W}}.
\]
Es un denominador común de la ventana actual, también para recompensas antiguas aún vigentes. No es normalización independiente por brazo ni una implementación de FRRMAB.

PH de descenso usa la media acumulada actualizada \(\bar r_t\), \(m_t=m_{t-1}+\bar r_t-r_t-\delta\), \(M_t=\min(M_{t-1},m_t)\), alarma si \(m_t-M_t>\lambda\) tras mínimo de observaciones. C5: δ=.0005, λ=.020, UCB1 c=.07. Reinicia crédito, no poblaciones ni archivo; el resondeo consume 150 FE del presupuesto regular. No es SW-UCB más PH.

La AUC reciente es el promedio trapezoidal del HV a lo largo de B FE:
\[
AUC_B=\frac1B\sum_t(FE_t-FE_{t-1})\frac{HV_t+HV_{t-1}}2,\quad (FE_0,HV_0)=(0,0).
\]
No es un área normalizada por el mejor algoritmo ni un AUC temporal. Mantener B y muestreo de 50 FE al comparar. El origen elegido penaliza el arranque; comparar campañas con otra definición requiere recalcularla.
"""
put('03_catalogo_algoritmos_portafolios.md','Catálogo de algoritmos y políticas',f"""
{vtable}
## Componentes individuales

**MOEA/D** descompone objetivos mediante Tchebycheff sobre valores normalizados, \(g(x|w,z^*)=\max_k w_k|z_k(x)-z_k^*|\), con el tratamiento de pesos nulos definido en código. Mantiene subproblemas, ideal y vecinos. En la campaña reciente: población 30, vecinos 6, probabilidad de selección local .9, máximo dos reemplazos y cruce 1.0.

**NSGA-II** aplica ordenamiento no dominado, crowding y selección ambiental elitista; conserva descendencia parcial al pausar un bloque. La población experimental es 30, aunque el constructor tiene otro valor predeterminado. Cruce .9. **SPEA2** utiliza fuerza S(i), fitness crudo R(i)=ΣS(j) de quienes dominan i y densidad 1/(σᵏ+2), k=floor(√n), con truncación de vecinos en objetivos normalizados. Población y archivo ambiental experimentales 30; cruce .9.

Los tres usan POX, intercambio de secuencia con probabilidad .2 y mutación de modo por gen 1/N en el código auditado. Un documento histórico menciona mutación .1, pero no es una especificación suficiente: el runner histórico invoca los constructores y la instantánea reciente establece el parámetro efectivo. No se homogenizaron operadores para esta auditoría.

Las diferencias de selección hacen razonable estudiar complementariedad; no garantizan regiones exclusivas ni superioridad del conjunto. Referencias originales: [MOEA/D](https://doi.org/10.1109/TEVC.2007.892759), [NSGA-II](https://doi.org/10.1109/4235.996017), [SPEA2, TIK 103](https://sop.tik.ee.ethz.ch/publicationlistfiles/zlt2001a.pdf). Son fundamento conceptual, no evidencia del comportamiento de esta implementación.

{formula}
""")

put('04_cambios_implementados.md','Qué se modificó, qué se conservó y por qué',f"""
Esta auditoría **no implementó cambios algorítmicos**. Reconstruye modificaciones preexistentes y conserva su [diff](evidence/preexisting_algorithm_changes.diff). El checkout inicial tenía modificados `arms.py`, `moead.py` y `spea2.py`, además de `cooperation.py`, scripts y resultados sin seguimiento Git. HEAD por sí solo no representa el experimento.

| Iteración | Limitación e hipótesis | Cambio aislado | Componentes conservados | Resultado / decisión |
|---|---|---|---|---|
| Observabilidad P4 | No era posible seguir identidad de soluciones | IDs y procedencia sin alterar RNG | Decodificador, objetivos y selección | Base `1d695f3`; no equivale a cooperación |
| I1 | Unión pasiva no transmite información genética | Segundo padre extranjero cada diez cruces; asignación reproducida del control | FE, poblaciones, selección ambiental, pesos, decoder | Ganancia media bajo replay; candidato condicionado |
| I2 | Crédito ΔHV pequeño frente al bono | Dividir explotación por máximo reciente | W,c, probes, operadores, archivo | Mejora confirmada respecto a SW-UCB |
| I3 | Posible suma de beneficios | Activar guía sobre escalado online | Misma cadencia y presupuesto | Sin ventaja adicional; no adoptado |
| PH histórico | Memoria vieja ante cambios de recompensa | Detector de descenso + reinicio de UCB1 | Poblaciones y archivo | Sin superioridad corregida; cerrado |

En los tres brazos el hook cooperativo se llama sólo al realizar cruce. Desactivado devuelve el padre nativo y no consume RNG adicional. Se añadió limpieza de guía al reset. No se inyectan incumbentes ni se asigna al hijo el fitness del donante. Cada nuevo hijo pasa por la evaluación nativa.

Las instantáneas `baseline`, `research_v1`, `research_v2` y `confirmation_frozen` están en la campaña reciente. Existe una corrección append-only de procedencia: las primeras filas leyeron hashes de disco después de cargar módulos, por lo que esos hashes no identifican por sí solos el código ya cargado. La corrección conserva la fuente base y un ensayo previo de reproducción de cinco controles. En esta tarea se verifican archivos y métricas guardadas, sin repetir esas optimizaciones.

No se atribuye el resultado de I3 a “incompatibilidad genética demostrada”. El cambio de descendencia modifica recompensas y decisiones futuras; la interacción es una hipótesis y exige controles adicionales.

Fuentes: [procedencia base](../portfolio_loop_20261015/baseline_execution_provenance.json), [protocolo](../portfolio_loop_20261015/protocol.md), {link('recent_paired_statistics')}. Para parámetros y fórmulas, [catálogo](03_catalogo_algoritmos_portafolios.md).
""")

inv_counts=read('instance_inventory_counts')
featurecols=['instance','jobs','machines','operations','modes_max','jobs_machines_ratio','processing_cv','machine_load_cv','relative_slack_mean','energy_mode_contrast_mean']
recentfeatures=inv[inv.instance.str.startswith('confirmation_')]
put('06_caracterizacion_instancias.md','Inventario completo y características estructurales',f"""
Se localizaron **2746 copias .dzn y 1336 contenidos distintos por SHA-256** en datos y directorios de instancias de los cuatro checkouts relacionados. El inventario incluye archivos históricos archivados de hasta **150×150 = 22500 operaciones**, además del conjunto expandido, perfiles f86, variantes pareadas, validación y las 14 bases recientes. Tener un archivo no implica disponer de un resultado experimental para él.

{table(inv_counts)}

El conjunto expandido declara **200 variantes, 40 bases: desarrollo 120 variantes de 24 bases y holdout 80 variantes de 16 bases**. Se inventarían las reservadas con metadatos, sin abrir su contenido para calcular características ni resultados. La campaña reciente añade 6 bases de desarrollo y 8 de confirmación interna. Esas ocho no son el test final. Los archivos sin split explícito se etiquetan `historical_or_unassigned`; no se convierten en confirmación a posteriori.

Hay 50 contenidos con errores de lectura bajo `data/invalid`, preservados sin corregir. No se presume que esos errores fueran generados intencionalmente para pruebas. `parsed` significa que se pudo caracterizar bajo el formato JSP2; no certifica factibilidad de cualquier calendario ni resuelve la instancia. Las copias idénticas comparten una fila y conservan todas las rutas en `copies`. [Detalle por archivo](tables/instance_file_copies.csv), [inventario por contenido](05_inventario_instancias.csv).

## Definiciones calculadas

| Familia | Definición operacional |
|---|---|
| Dimensión | J, M, N=J×M del formato, modos mínimo/máximo, J/M, operaciones por trabajo y máquina |
| Procesamiento | Por operación se promedia duración entre sus modos; media, DE poblacional y CV entre operaciones. Se guardan también media/min/max de todos los modos |
| Cargas | Lₘ=Σₒ∈ₘ promedio de duración por modos; CV(L), max(L)/media(L), vector completo por máquina |
| Concentración | HHI de cantidades de operaciones por máquina, Σ(nₘ/N)²; aquí las rutas completas la fijan en 1/M. El desequilibrio temporal puede variar aunque el conteo sea uniforme |
| Fechas | Estadísticos de releases por operación y due date de última operación tecnológica; finalización aislada más rápida qⱼ por recurrencia max(release,fin previo)+mínimo tiempo |
| Holgura | sⱼ=(dⱼ−qⱼ)/Σmínimo tiempo del trabajo; proporción ajustada sⱼ≤0. Es un criterio explícito y conservador: no incluye contención entre trabajos |
| Energía | Media/CV entre energías medias por operación; razón max/min entre modos; energía del modo más rápido menos la del más lento |
| Conflicto | Correlación de Pearson tiempo–energía **dentro de cada operación**, luego promedio. Evita confundir operaciones grandes con modos rápidos |
| Estructura | Cadena máxima, cargas, holgura, cota inferior/superior de Cmax y energía; descriptores, no demostración de dificultad real |

Cada operación requiere una máquina fija y cada trabajo visita M máquinas en estos datos. La longitud de precedencias es M. El número de modos se documenta, pero es constante (5) en las bases de comparación principales: no puede estimarse su efecto algorítmico con esas corridas.

## Confirmación interna: características reales
{table(recentfeatures,featurecols,4)}

El lector vectorizado permite caracterizar el archivo histórico grande sin optimizar. Se contrastó con el lector de dominio y sus cotas en bases recientes, históricas y dos de las mayores instancias; los errores numéricos máximos fueron 1.42×10⁻¹⁴. Véase {link('independent_feature_checks')}. No se infiere que una mayor carga o un mayor N cause necesariamente menor calidad normalizada.

{fig('08_caracterizacion')}
{fig('21_perfiles_instancias')}
{fig('22_modos_energia')}
""")

put('07_clasificacion_tamanos.md','Clasificación reproducible del tamaño',f"""
Se usan categorías **descriptivas del diseño experimental de ocho geometrías**, no una taxonomía universal del JSSP. Las geometrías de referencia son 5×5, 10×10, 20×10, 10×20, 20×20, 30×20, 40×20 y 50×50, con N=[25,100,200,200,400,600,800,2500]. Se calculan los terciles empíricos con interpolación lineal (NumPy/Pandas): Q₁/₃=200 y Q₂/₃=533.333.

| Categoría de este informe | Regla | Geometrías observadas de referencia | Bases de confirmación |
|---|---|---|---|
| Pequeña | N≤200 | 5×5, 10×10, 20×10, 10×20 | 4 |
| Mediana | 200<N≤533.333 | 20×20 | 1 |
| Grande | N>533.333 | 30×20, 40×20, 50×50 | 3 |

Se conservan juntos los dos diseños de 200 operaciones. Eso produce grupos desbalanceados; no se fuerzan cortes para obtener un ganador determinado. Los archivos archivados mayores también se etiquetan por esta regla, pero “grande” cubre desde 600 hasta 22500 operaciones: para describirlos se deben mirar N y geometría exactos. La columna del CSV es `geometry_category`.

La relación J/M y las dos dimensiones se conservan separadas: 20×10 y 10×20 tienen N=200 pero distinta contención y longitud de cadena. No se reduce toda la estructura a un único número. Las instancias de validación de 2×2, 3×2 y 3×3 no definen los cortes ni entran en inferencia de rendimiento.

La literatura usa familias de benchmarks y dimensiones concretas, sin un umbral único que pueda trasladarse automáticamente a este MO-JSSP con tres objetivos, releases y velocidades. Por eso este informe no etiqueta estos terciles como categorías generales de la literatura. Una comparación con un benchmark externo debe publicar sus propias dimensiones, objetivos, generador y presupuesto.

La categoría mediana tiene una sola base en confirmación. Un intervalo bootstrap idéntico a su valor observado no es precisión perfecta: no hay información para estimar variación entre bases en esa categoría. Se informa como **incertidumbre entre bases no estimable**.

Ver [resultados por tamaño](08_rendimiento_por_tamano.md), {link('algorithm_by_size')} y [registro del criterio](evidence/analysis_audit.json).
""")

put('08_rendimiento_por_tamano.md','Qué algoritmo funciona mejor por tamaño',f"""
La tabla siguiente compara sólo **confirmación interna reciente a 3000 FE**. Primero se promedian las tres semillas por base. Cada base pesa igual. Los cortes se definieron por el diseño dimensional, sin mirar ganadores.

{size_table}

MOEA/D tiene mayor HV medio en las tres categorías. Esto no demuestra una especialización universal: pequeña contiene cuatro bases heterogéneas; mediana sólo una; grande tres. En la menor base individual (5×5), SPEA2 obtiene la mayor media y NSGA-II también supera a MOEA/D. En las otras siete gana MOEA/D. La agrupación “pequeña” oculta esa excepción.

## Instancias y ganadores exactos
{table(winner)}

## Diferencias históricas que no deben ocultarse

En Fase 1, con 1000 FE y ocho bases por cinco perfiles, NSGA-II presenta ventajas medias en ciertas geometrías intermedias-altas. El presupuesto, las semillas y las bases son otros. No corresponde sumar esas filas a la confirmación de 3000 FE ni concluir que un algoritmo “dejó de especializarse”. El [archivo de ganadores](tables/best_algorithm_by_instance.csv) contiene todas las campañas compatibles por separado; {link('algorithm_by_size')} muestra tamaños de muestra, media, DE e intervalos.

Las desviaciones de las semillas en la figura describen variación estocástica de esa base. No representan incertidumbre sobre todas las instancias de igual dimensión. Harían falta varias bases independientes por geometría y perfiles cruzados para esa afirmación.

{fig('09_hv_tamano')}
{fig('01_hv_confirmacion')}
""")

put('09_rendimiento_por_caracteristicas.md','Rendimiento y características de instancia',f"""
Se estudió la diferencia HV(NSGA-II o SPEA2) − HV(MOEA/D), no sólo el HV absoluto. Las correlaciones de Spearman usan medias de semillas por base; Fase 1 restringe este análisis a los ocho perfiles nominales para no presentar 40 variantes correlacionadas como independientes. Se conservan separadas las campañas y los presupuestos. No se ajusta un modelo de nueve predictores con ocho observaciones.

Los descriptores incluyen operaciones, J/M, CV de carga por máquina, holgura, CV de procesamiento, contraste energético, releases y correlación tiempo–energía. El número de modos es constante y se marca no estimable. Las correlaciones son exploratorias sin pruebas de selección de variables ni reivindicación causal.

## Contrastes emparejados de perfiles históricos

Fase 1 permite comparar cada tratamiento con su propia base nominal. Para separar el cambio de rendimiento relativo se calcula:

Δrel=(HV_alg−HV_MOEAD)_perfil−(HV_alg−HV_MOEAD)_base.

Se promedian cinco semillas antes de calcular diferencias entre las ocho bases. Se corrigen conjuntamente ocho contrastes (4 perfiles × 2 algoritmos). Esto controla dependencia de variantes, pero no convierte los cambios de HV entre instancias normalizadas de forma distinta en pérdida física de tiempo o energía.

{table(profile,['profile','contrast','n_base_clusters','mean_delta','ci_low','ci_high','wins','losses','p_signflip','p_holm'])}

El cuello de botella aumenta la ventaja relativa de NSGA-II frente a MOEA/D en las ocho bases (+0.014506 HV medio), señal consistente. Tras Holm sobre ocho contrastes, p=.0625: merece contraste dirigido, no una regla confirmada de especialización. El perfil energético fuerte también muestra una señal nominal para NSGA-II, debilitada al corregir multiplicidad. Los cambios de fechas tienen incertidumbre que incluye cero en estos contrastes relativos.

En la campaña reciente tamaño y perfil se asignan juntos: 20×10 con energía fuerte, 10×20 con cuello de botella, 20×20 con duración variable y 30×20 con releases altos. Una correlación no identifica cuál de ellos explica la diferencia. Además, las cotas analíticas modifican la escala entre perfiles. Los mismos métodos sí comparten normalización dentro de cada instancia.

Fuentes: {link('profile_relative_effects_by_base')}, {link('exploratory_feature_correlations')}, {link('feature_performance_scatter')}.

{fig('14_correlaciones')}
{fig('18_caracteristicas_rendimiento')}
""")

put('10_especializacion_algoritmica.md','¿Existe evidencia de especialización algorítmica?',"""
**No hay evidencia suficiente para afirmar una regla general que asigne un algoritmo a un tipo o tamaño de instancia. Sí hay heterogeneidad y señales locales que justifican investigar esa posibilidad.**

Se observan excepciones claras a una superioridad uniforme de MOEA/D: SPEA2 y NSGA-II lo superan en la base 5×5 de confirmación, y existen victorias históricas a 1000 FE. También hay evidencia exploratoria de sensibilidad relativa al cuello de botella: el contraste emparejado de NSGA-II es positivo en 8/8 bases históricas, pero la familia de ocho pruebas corregidas no supera el umbral del 5%. No significa que el efecto sea inexistente; la precisión y el diseño todavía limitan la generalización.

| Propiedad | Qué permiten los datos | Qué falta |
|---|---|---|
| Ganador de una base | Comparación de medias y dispersión de semillas a igual FE | Replicar la generación de bases con la misma característica |
| Tamaño | Asociaciones por N y geometría exacta | Varias bases por tamaño con perfiles cruzados |
| Carga | Contrastes relativos de tratamiento histórico | Nueva confirmación dirigida e independiente |
| Holgura/energía | Sensibilidad al perfil y correlaciones | Cotas comparables, efectos físicos y diseño cruzado |
| Modos | Descripción de cinco modos | Corridas existentes con cantidades variables; no están en cohortes principales |
| Generalización | Confirmación interna del escalado | Test final sin abrir y familias externas |

Para resolverlo, conviene acordar antes de usar el test una hipótesis acotada, por ejemplo “el cuello de botella cambia la ventaja NSGA-II frente a MOEA/D”. Se necesitan bases independientes replicadas en varias geometrías, tratamiento emparejado con la misma ruta/duraciones base, semillas comunes y un único presupuesto principal. El número de bases debe justificarse mediante precisión o potencia con el efecto piloto y un mínimo relevante, no sólo aumentando semillas.

La evaluación debe agrupar por base y probar la interacción algoritmo×tratamiento. Un clasificador multivariable entrenado con ocho bases por campaña sería frágil. Si se usan modelos predictivos, separar por familias/base al validar y mantener el holdout final intacto. La auditoría y el diseño se pueden discutir antes de la reunión; las nuevas optimizaciones deben quedar para después de acordar el protocolo.

La complementariedad regional de frentes tampoco equivale a especialización por instancia. Dos algoritmos pueden producir soluciones diferentes de una misma base sin que uno sea el mejor método para una familia entera.

Evidencia: [tamaño](08_rendimiento_por_tamano.md), [características](09_rendimiento_por_caracteristicas.md), [contrastes de perfiles](tables/profile_relative_effects.csv).
""")

put('11_comparacion_standalones_portafolios.md','Comparación integral por condiciones compatibles',f"""
## Comparación principal: confirmación reciente

3000 FE por ejecución, población 30, bloques 50, ocho bases nuevas y tres semillas por base. Media con peso igual por base. El padre externo usa una asignación obtenida de otra ejecución: la tabla muestra el coste del tratamiento, no el del par control+tratamiento.

{main_table}

MOEA/D lidera HV y AUC medios. Escalado mejora el portafolio original y uniforme, pero no supera en promedio a los tres individuales. NSGA-II y SPEA2 también tienen AUC media mayor que escalado. La diversidad genética más alta del portafolio no compensa automáticamente esa brecha de calidad.

## Diagnóstico histórico, sin mezclar presupuestos
{table(hc[hc.campaign=='phase2_budget'],['budget','method','n_base_clusters','mean_hv','sd_hv','mean_seconds'])}

La ventaja de MOEA/D histórico respecto al portafolio original no desaparece al pasar de 1000 a 5000 FE. Eso contradice una explicación basada exclusivamente en arranque: puede influir profundidad, asignación o complementariedad insuficiente. No identifica por sí solo sus causas.

Las otras cohortes (benchmark técnico, Fase 1, PH y versiones F8) se publican en {link('historical_summary')}, con su presupuesto y composición. Los métodos de PH no comparten las variantes de perfil ni todas las semillas con Fase 2. No se integran como si sus HV medios midieran un mismo ensayo. Tampoco hay una campaña reciente de 10000 FE que permita concluir superioridad a ese presupuesto.

## Métricas disponibles y límites

HV, FE, archivo y tiempo existen en cohortes principales. AUC reciente se recalculó con los 60 bloques. Los rangos y distancias en objetivos, y las distancias genéticas finales, son diagnósticos diferentes. Los archivos históricos guardan vectores pero no todos los genotipos ni poblaciones. No se completa con números inventados la diversidad genotípica histórica.

Las tablas de medias, medianas, DE, IC y contrastes están en {link('recent_summary')}, {link('recent_paired_statistics')} y {link('exploratory_all_pairwise')}. El conjunto principal es confirmación interna; resultados de desarrollo y perfiles son exploratorios.

{fig('03_hv_fe')}
{fig('13_presupuestos_historicos')}
""")

put('12_analisis_estadistico.md','Estadística, incertidumbre y unidad de análisis',f"""
La unidad independiente es la **base de instancia**. Se promedian semillas dentro de base; en Fase 1 también perfiles al comparar rendimiento global. Sus 600 corridas equivalen a ocho clústeres independientes, no 600 bases. En confirmación reciente n=8 con 24 corridas por método; en desarrollo n=6. Fase 2 tiene n=10, 150 trayectorias, 450 cortes dependientes.

## Familia principal predefinida

Dos candidatos frente a SW-UCB en HV final de confirmación, Holm de dos pruebas. Se recalculan diferencias pareadas, bootstrap de bases (20000 remuestreos, semilla analítica 20261016), prueba exacta de inversión de signos de la media (2⁸), victorias/empates/derrotas y dᶻ.

{primary_table}

El escalado presenta ΔHV=+0.020680 e IC positivo, con p ajustado .015625. El padre externo tiene ΔHV=+0.008539 e IC bootstrap positivo, pero p ajustado .054688. No se elige la prueba que produzca “significativo”: sus distintos resultados se muestran juntos. La prueba de signos sin magnitudes para guía da .070312, frente a .054688 de inversión de signos de la media.

La prueba de inversión de signos exige intercambiabilidad/simetría bajo la hipótesis nula; no es idéntica al test binomial de signos ni prueba causal por sí sola. dᶻ divide por la DE de diferencias entre bases y puede ser inestable con n pequeño. Los IC bootstrap son aproximados, condicionados a la colección de bases y no simultáneos. Los IC descriptivos de HV absoluto mezclan estructura y escala de normalización; para cambios convienen IC de diferencias pareadas.

## Análisis secundarios y exploratorios

AUC, tiempo, archivo y diversidad se reportan como secundarios con sus IC; no se declararon todos confirmatorios al 5%. Se incluyen Friedman exploratorio y comparaciones por pares con Holm **por cohorte y presupuesto** en {link('omnibus_tests')} y {link('exploratory_all_pairwise')}. Un omnibus significativo no demuestra que cada método sea mejor que todos los demás. Los contrastes de ocho perfiles relativos tienen su propia familia de ocho pruebas en {link('profile_relative_effects')}.

Las p de Wilcoxon calculadas con SciPy pueden usar métodos distintos en presencia de ceros/empates; la tabla conserva además el contraste exacto de inversión de signos. Las p históricas de PH documentadas (.146484, .320312, .578125 tras Holm) se citan como análisis histórico, no como una nueva confirmación. No confundir ausencia de significación con equivalencia.

No se realizó metaanálisis de campañas, selección de variables ni ajuste del portafolio. La nueva semilla de bootstrap puede cambiar ligeramente los límites frente al informe del día 15 sin cambiar los resultados crudos. Los intervalos de una categoría con una sola base son degenerados y **no estiman** incertidumbre entre bases.

{fig('02_diferencias_pareadas')}
""")

th=threshold[threshold.split=='confirmation'].groupby('method').agg(reached=('reached','sum'),runs=('reached','size'),mean_capped_FE=('FE','mean'),mean_capped_seconds=('seconds','mean')).reset_index()
timebase=bs[bs.split=='confirmation'].pivot(index='instance',columns='method',values='seconds');timepct=100*(timebase.scaled/timebase.adaptive-1)
put('13_eficiencia_computacional.md','Coste computacional y rendimiento por presupuesto',f"""
## Calidad y tiempo a 3000 FE
{table(means,['Método','HV','AUC-HV','Tiempo (s)'])}

Frente a SW-UCB original, escalado aumenta el tiempo medio de búsqueda un **1.46%** y padre externo un **4.59%**, usando el cociente de medias. No son porcentajes medios por instancia ni medidas aisladas de overhead. En 5×5, escalado aumenta el tiempo **{timepct.loc['confirmation_00_5x5']:.1f}%**: la condición global de coste no garantiza una mejora temporal en todas las bases. Los tiempos no son un benchmark de hardware portátil y los datos previos se midieron en otro contexto temporal.

## FE para alcanzar el HV final del control original
{table(th)}

El escalado alcanza el objetivo pareado en 22/24 ejecuciones. La media de FE truncada a 3000 es 2062.5, pero los dos casos que no llegan están censurados. No significa que todos alcancen el objetivo en ese presupuesto ni que exista un ahorro garantizado. La comparación completa está en {link('threshold_baseline_final_hv')}; conservar tasa de éxito y distribución, no sólo media truncada.

El tratamiento de padre externo cuesta 3000 FE, pero obtener la asignación SW-UCB específica requiere otras 3000 FE desde cero. Si se presenta como procedimiento completo, son 6000 FE y suma de ambos tiempos. La comparación con control de replay es causal para el cambio de variación condicionado a esa asignación; no prueba eficiencia total de una política autónoma de 3000 FE.

No hay cronómetros separados que permitan atribuir exactamente segundos a selección, normalización, archivo, donante y selección ambiental. `block_seconds` incluye la ejecución del brazo; `elapsed` captura el proceso de búsqueda. Se reporta el tiempo total y se evita deducir overhead mediante diferencias entre algoritmos con frentes de distinto tamaño.

La auditoría actual consume **0 FE de optimización**. Recalcular HV desde objetivos guardados no busca soluciones. El informe original contabiliza 936000 FE de tratamientos, 15000 de reproducción y auditorías por separado; estos costes no se vuelven a cargar como nuevas corridas.

{fig('04_calidad_tiempo')}
{fig('23_hv_tiempo')}
""")

us=un.groupby(['FE_per_arm','arm']).agg(contribucion_exclusiva=('marginal_hv','mean'),ganancia_union=('union_gain','mean')).reset_index()
put('14_complementariedad.md','Complementariedad observada y beneficio real',f"""
**Sí existe complementariedad geométrica observada. No se ha demostrado que baste para compensar el presupuesto dividido.** Los archivos de los tres algoritmos contienen soluciones diferentes; la unión mejora el HV del mejor archivo aislado en muchos casos. Sin embargo, esa unión compara tres búsquedas completas y cuesta tres veces el presupuesto de cada una.

## Medida canónica

Sea Aᵢ el archivo completo guardado de cada brazo y U=ND(∪Aᵢ). La contribución exclusiva es

MCᵢ = HV(U) − HV(ND(∪ⱼ≠ᵢ Aⱼ)).

Al retirar i, se recuperan las soluciones de otros archivos que estaban dominadas por él. Restar sus puntos del frente U ya filtrado pierde esos sustitutos y sobreestima MCᵢ. Se detectó ese defecto en el cierre histórico; los resultados originales no se modificaron aquí. El recálculo actual coincide con la tabla histórica canónica.

{table(us)}

A 5000 FE por individual (15000 para la unión), los aportes exclusivos medios son aproximadamente .030796, .003065 y .003849 para MOEA/D, NSGA-II y SPEA2. La ganancia de unión sobre el mejor individual a ese B es .009547. Estos números no son un beneficio gratuito de un portafolio de 5000 FE. Tampoco se suman los MC como HV total: el volumen cubierto en común permanece sin asignación exclusiva.

En el portafolio reciente se calcula la misma eliminación sobre los archivos locales **realmente obtenidos bajo su asignación**. El valor no predice qué pasaría si se retirara un algoritmo y se reasignaran sus FE: es un contrafactual geométrico, no una ablación de búsqueda. La complementariedad puede variar al cambiar cuánto ejecuta cada brazo.

## Cuatro afirmaciones distintas

| Concepto | Evidencia actual |
|---|---|
| Complementariedad observada | Archivos y HV exclusivos positivos, heterogéneos por base |
| Especialización regional | Ejemplos y descriptores de regiones; falta persistencia por semillas y bases |
| Especialización por tipo | Señales de perfiles; insuficiente validación independiente |
| Beneficio del portafolio | Escalado mejora su control, pero los individuales siguen siendo referencias más fuertes |

En los 42 pares recientes, el uniforme a 3000 FE equivale a la unión de los tres flujos individuales a 1000 FE con semillas alineadas, según la auditoría conservada. Es una demostración de agregación pasiva, no de cooperación activa.

Fuentes: {link('historical_standalone_union')}, {link('recent_complementarity')}, [corrección histórica](../pareto_cooperation_research/metrics_correction_report.md).

{fig('20_complementariedad_fe')}
""")

put('15_espacio_objetivos.md','Regiones del espacio objetivo y diversidad',f"""
Se muestran frentes **observados**, no el Pareto óptimo verdadero. Las proyecciones 2D pueden ocultar dominancia en la tercera coordenada. Un punto extremo en Cmax puede empeorar E; una nube visualmente más amplia puede añadir muy poco HV exclusivo.

Las figuras ilustrativas usan la base histórica `base_c02_10x10_b03_tard_high`, semilla 42, 3000 FE por individual. Se eligió una base histórica identificada, no un gráfico agregado de objetivos de instancias incompatibles. La unión cuesta 9000 FE. El CSV conserva valores físicos de instancia y normalizados, algoritmo y pertenencia al ND conjunto.

{fig('07_frentes_proyecciones')}
{fig('19_frente_3d')}

La diversidad en objetivos se describe mediante número de vectores distintos, rango por objetivo y distancia euclidiana media al vecino más cercano tras normalizar. El rango no mide cobertura uniforme ni convergencia. NN puede aumentar por dispersión o por pérdida de puntos; disminuir por mayor densidad útil o por concentración. Se debe leer junto con HV y cardinalidad, no etiquetar automáticamente “mayor NN = mejor”.

La diversidad genética registrada es la media de distancias entre pares de la población interna de cada brazo: fracción de posiciones distintas en secuencia y modos, promediadas con peso 1/2. Se promedia por brazo en la campaña. Las poblaciones internas de MOEA/D, NSGA-II y SPEA2 tienen semánticas de selección distintas. El número mide dispersión genotípica, no diversidad de calendarios fenotípicamente distintos: dos genotipos pueden decodificar de manera similar.

Los archivos finales sí permiten volver a calcular solapamiento exacto genotípico/objetivo. No permiten reconstruir toda la población usada para la diversidad registrada ni todos los hijos evaluados y descartados; reproducirlos exigiría nuevas corridas, excluidas de esta tarea. Los descriptores de rango por base están en {link('objective_ranges')} y los frentes en {link('recent_final_fronts')}.

No se ha identificado una región que pertenezca establemente a un algoritmo para todas las bases o perfiles. Para demostrarlo se necesita definir regiones antes del contraste, estimar ocupación y aporte exclusivo por base/semilla y comprobar persistencia, controlando FE. Los gráficos actuales fundamentan exploración, no esa generalización.

{fig('16_solapamiento')}
""")

cs=comp[(comp.split=='confirmation')&comp.method.isin(['adaptive','scaled','guidance'])].groupby(['method','arm']).agg(MC=('marginal_hv','mean'),genotipos_exclusivos_ND=('exclusive_genotypes_in_union_nd','mean'),compartidos=('shared_genotypes','mean')).reset_index()
put('16_contribuciones_por_brazo.md','Aporte exclusivo, procedencia y solapamiento',f"""
Las siguientes medias usan ocho bases y tres semillas de confirmación a 3000 FE totales. Los archivos locales contienen los resultados de cada receptor bajo la asignación ejecutada. Un genotipo presente en dos archivos cuenta como compartido y la eliminación de un brazo conserva la copia del otro.

{table(cs)}

No se equipara el brazo receptor con origen genético completo. `first_observed_final` es el primer brazo en cuyo archivo se observó el genotipo durante el registro por bloques; no captura todos los hijos descartados ni su genealogía. `guidance_events` identifica receptor, donante y padre nativo sustituido. Un hijo del donante puede tener crédito de generación del receptor y ascendencia de otro brazo. Son datos distintos.

El recálculo offline de todos los MC recientes discrepa de los valores guardados como máximo 4.44×10⁻¹⁶. El Jaccard exacto por genotipos y vectores se publica por par de brazos en {link('archive_overlap')}. Cero coincidencias no prueba ausencia de solapamiento volumétrico ni regiones completamente separadas.

Hay tres escalas temporales disponibles: recompensas por bloque (ganancia secuencial dependiente del orden), MC de archivos recientes finales y MC de uniones individuales históricas a 1000/3000/5000 FE. **No hay archivos locales completos por cada bloque reciente** para calcular un MC temporal canónico continuo. Asignar a un brazo la suma de ΔHV de sus bloques no sustituye ese análisis: una ganancia temprana puede volverse redundante después.

Las contribuciones por instancia, semilla y presupuesto están en {link('recent_complementarity')} y {link('historical_standalone_union')}. Para estudiar si una región cambia con las características se necesita cruzar perfiles con bases independientes y guardar archivos locales/procedencia por checkpoint. Esa optimización queda como trabajo posterior.

{fig('06_contribuciones')}
""")

allocation_summary=alloc[(alloc.split=='confirmation')&alloc.method.isin(['uniform','adaptive','scaled','guidance'])].groupby(['method','arm']).FE_share.mean().unstack().reset_index()
put('17_analisis_adaptabilidad.md','Selección adaptativa: conducta y utilidad',f"""
El selector original ya responde matemáticamente a recompensas, pero el tamaño del bono frente a ΔHV puede volverlo casi uniforme. Escalado corrige la escala de explotación sin eliminar revisitas ni cambiar W o c. Las [fórmulas exactas](03_catalogo_algoritmos_portafolios.md) evitan confundirlo con FRRMAB o con normalizar cada brazo por separado.

## Respuestas a las seis preguntas

| Pregunta | Evidencia y alcance |
|---|---|
| ¿Reparto no uniforme? | Sí: escalado cambia las cuotas medias y los patrones por bloque |
| ¿Reacciona a recompensas? | Sí por reconstrucción de términos de ventana y reglas; el crédito es relativo al estado global |
| ¿Favorece progreso reciente? | La explotación escalada hace relevante su media reciente; no garantiza escoger al futuro mejor brazo |
| ¿Difiere entre instancias? | Sí en las trayectorias y cuotas observadas; no prueba un predictor de características |
| ¿Mejora uniforme? | ΔHV medio +.023649 en confirmación, 8/8 bases; contraste secundario/exploratorio |
| ¿Mejora SW-UCB original? | Sí en esta confirmación interna: ΔHV +.020680, Holm .015625 en familia principal |

{table(allocation_summary)}

El original asigna aproximadamente 34.44/32.71/32.85% a MOEA/D/NSGA-II/SPEA2. Escalado pasa a 40.83/25.83/33.33%. Esto concuerda globalmente con la ventaja de MOEA/D, pero aún deja la mayoría del presupuesto fuera de él. La base 5×5 y las trayectorias intermedias impiden convertir el resultado agregado en “asignar todo a MOEA/D” como política adaptativa demostrada.

La causalidad identificada por I2 es el efecto total de cambiar la regla de escala, con todo lo demás fijo en los controles. No permite afirmar que cada FE adicional a MOEA/D causó la mejora ni que toda desigualdad de cuotas sea adaptación eficaz. El estado de cada algoritmo cambia con la historia de ejecución.

La generalización a nuevas familias/test no se ha demostrado. La confirmación utiliza nuevas bases pero repite la relación tamaño–perfil y el mismo generador.

{fig('05_asignacion')}
{fig('15_trayectorias_asignacion')}
""")

u=read('ucb_terms');uscale=u[(u.split=='confirmation')&(~u.probe)].groupby('method')[['window_mean','exploitation','exploration']].median().reset_index()
put('18_analisis_recompensas.md','Crédito de hipervolumen y escala del selector',f"""
La recompensa es rₜ=max(0,HVₜ−HVₜ₋₁), calculada después de actualizar el archivo global con soluciones evaluadas. Es marginal al **archivo presente**, no al archivo local ni al Pareto óptimo. Cada bloque reciente usa 50 FE; el mismo ΔHV representa diferente dificultad en diferentes momentos de búsqueda. La primera gran ganancia de arranque no se aprende en el warmup neutral.

La reconstrucción utiliza exclusivamente las observaciones anteriores a cada decisión, ventana global de diez, recuentos por brazo y escala compartida. Se excluyen warmup y probes del resumen de términos. Valores infinitos por ausencia de un brazo se representan como no aplicables a la mediana, no como cero.

{table(uscale)}

La [auditoría histórica Fase 2](../expanded_portfolio_phase2/final_closure/f2_6_reproducibility_manifest.json) registró explotación .00169 frente a exploración .05978, razón 35.37, y verificó 2910 decisiones. Son cifras históricas de esa cohorte; el resumen anterior se recalcula en las nuevas bases. Escalado eleva la relevancia de la explotación, sin cambiar la recompensa cruda guardada.

Una ventana enteramente nula usa escala uno y el bono mantiene exploración. El brazo ausente vuelve a ser elegible con UCB infinito. Se evita descarte irreversible, pero puede pagarse exploración cuando un brazo no recuperará progreso. En sentido opuesto, ceros globales pueden ocultar aprendizaje local o capacidad futura: suprimirlos indiscriminadamente sería metodológicamente injustificado.

## Límites de crédito

El hijo de un padre externo se acredita al receptor. El donante puede generar una mejora retardada en otro algoritmo sin recibir recompensa inmediata. HV además favorece ganancias de volumen y no toda región complementaria. No existen trazas de ascendencia completa ni un tratamiento de recompensa retardada que permita cuantificar ese sesgo causalmente. Es una hipótesis abierta, no un fallo demostrado de todo uso de HV.

Datos por decisión: {link('ucb_terms')}; por bloque: {link('recent_blocks')}. El diagnóstico no recalibra c ni W ni selecciona una nueva configuración.

{fig('11_escala_ucb')}
""")

st=stale[(stale.split=='confirmation')&stale.method.isin(['uniform','adaptive','scaled','guidance'])].groupby('method')[['FE_after_two_own_zero_gains','positive_recoveries','max_idle_blocks']].mean().reset_index()
put('19_asignacion_presupuesto.md','Asignación, estancamiento y revisitas',f"""
Los tres primeros bloques de cada portafolio reciente son neutrales, seguidos por tres probes adaptativos. El presupuesto se cuenta por evaluaciones reales, incluida la inicialización. Se verificó que los 312 registros suman exactamente 3000 FE y 60 bloques. No se interpreta una generación parcial como una generación completa ni se supone que pausar pierda el estado interno.

{table(allocation_summary)}

## Estancamiento operacional

Se define una racha propia de ceros como bloques del mismo brazo con ΔHV global≤10⁻¹⁴, aunque entre ellos hayan actuado otros algoritmos. Se contabilizan FE al revisitarlo tras dos ceros, recuperaciones positivas y máximo de bloques ociosos. Son descriptores auditables de una trayectoria, no una etiqueta definitiva de inutilidad.

{table(st)}

Escalado reduce modestamente FE gastadas tras dos ceros frente al original (250 a 220.83 por corrida), pero también se observan menos recuperaciones de ese tipo y mayores pausas máximas. No demuestra “recuperación mejorada”. El padre externo, con asignación idéntica, cambia las recompensas y las rachas, lo que muestra por qué estancamiento y decisiones no se pueden interpretar aisladamente.

Las etapas de búsqueda pueden reconstruirse con FE en {link('recent_blocks')}: temprano≤1000, medio1000–2000, tardío2000–3000, dejando warmup separado. Esos cortes son descriptivos, no nuevos presupuestos independientes. Se entrega además la secuencia de brazo seleccionado en 24 filas por política, para evitar que una media oculte comportamientos distintos entre semillas.

El coste de inicializar tres poblaciones de 30 es al menos 90 evaluaciones, frente a 30 en un individual. Los bloques neutrales asignan 150 FE en total, de las cuales una parte ya continúa la búsqueda después de inicializar. No se debe llamar a las 150 FE “pérdida por inicialización”: incluyen trabajo útil. La desventaja de profundidad se discute como hipótesis en [H1–H7](22_por_que_no_supera_moead.md).

{fig('17_estancamiento')}
""")

put('20_analisis_cooperacion.md','Padre externo y cooperación activa',f"""
**Compartir genotipos mejora descriptivamente el portafolio original bajo la asignación controlada, pero no está demostrado como la mejor política autónoma ni supera a MOEA/D a igual FE de tratamiento.**

## Mecanismo observado en código

1. El selector/replay determina el receptor del siguiente bloque; el donante no determina el receptor.
2. Se toma el ND global actual. Los candidatos deben ser de la misma instancia, estar ausentes del archivo local y tener primera observación en otro brazo.
3. Se escoge el candidato que maximiza su distancia mínima euclidiana en objetivos normalizados al archivo local. Empates por ID genotípico. Un solo donante queda congelado durante el bloque.
4. Cada brazo mantiene un contador persistente de eventos de cruce exitoso. Cada diez oportunidades sustituye el segundo padre nativo por el donante disponible; no consume sorteos adicionales para elegir cadencia.
5. POX y mutación nativos generan descendencia. Toda evaluación consume FE y actualiza selección ambiental/decomposición nativas. No se copia el fitness del padre al hijo.
6. Se actualizan archivo local, global y crédito del receptor. La frecuencia efectiva depende de disponibilidad de donante y de la tasa nativa de cruce; no es exactamente una transferencia cada diez FE.

No se mezclan instancias ni máquinas, no se reemplazan poblaciones y no se cambia el problema. Los registros de eventos conservan receptor, padre sustituido, donante e índice de cruce.

## Comparación controlada y coste

El tratamiento `guidance` reproduce **exactamente la secuencia de asignación de SW-UCB del control**, incluidos presupuestos y fases, para aislar el intercambio genético. La auditoría previa verifica 42 pares con asignaciones idénticas y genotipos finales distintos. La confirmación usa ocho bases y tres semillas.

{primary_table}

Guía obtiene ΔHV +.008539, ΔAUC +.007885, diversidad genética media +11.84% y coste temporal medio +4.59%. HV mejora en 7/8 bases y cae en 10×10. La p corregida HV .054688 impide presentarlo como resultado confirmatorio fuerte al 5%, aunque el IC bootstrap sea positivo. El efecto es condicionado al replay: ejecutar ambos desde cero cuesta 6000 FE.

## Por qué aumenta diversidad sin el mejor HV

El donante distante altera combinaciones genéticas y puede ampliar rangos sin desplazar la superficie hacia el ideal ni cubrir una región de gran volumen exclusivo. La distancia genotípica no mide convergencia; rango no equivale a cobertura. El archivo y la selección nativa pueden descartar hijos distantes de baja calidad. La información puede ser redundante en volumen aun sin coincidir sus vectores. Estos mecanismos son explicaciones plausibles, coherentes con los indicadores, pero no se midió el destino de todos los hijos para atribuir cuál domina.

{fig('10_cooperacion_diversidad')}
""")

comb=pa[(pa.split=='development')&(pa.treatment=='combined')&(pa.control=='scaled')]
put('21_analisis_combinacion_mecanismos.md','Por qué la combinación no añade una mejora demostrada',f"""
I3 agrega el mismo padre externo a UCB escalado y utiliza decisiones online. A diferencia del tratamiento de guía aislado, no necesita un control previo de asignaciones. La comparación causal primaria de esta iteración es combinado − escalado, con igual FE, operadores y seis bases de desarrollo × tres semillas.

{table(comb,['metric','n_bases','mean_delta','ci_low','ci_high','wins','losses','p_signflip'])}

El ΔHV medio es −.001742, IC que incluye cero, tres bases favorables y tres desfavorables. ΔAUC es −.002773, favorable en dos de seis bases. La diversidad genética media sube ligeramente, mientras HV y cardinalidad no acreditan una ganancia. Se decidió **no adoptarlo ni llevarlo a confirmación**, no declarar que siempre perjudica.

Hay una interacción real en el flujo: el padre externo cambia hijos, archivos y recompensas; escalado convierte esas recompensas en decisiones que alteran qué algoritmo recibe más profundidad. La ganancia condicional de guía con replay no se puede sumar algebraicamente a la ganancia de escalado. El resultado combinado no sigue la misma asignación que ninguno de los controles.

Hipótesis pendientes: donantes distantes poco útiles bajo la nueva asignación; cambios de crédito que desvían FE; información redundante después de que escalado profundiza el brazo fuerte; o incertidumbre estocástica con pocas bases. Ninguna se identificó mediante un factorial completo con replay común a las cuatro celdas. No elegir retrospectivamente sólo las bases favorables ni ajustar la cadencia usando confirmación.

Un siguiente ensayo debe acordar una ablación con asignación común: sin guía y con guía bajo trazas fijas SW-UCB y escalado, más políticas online claramente diferenciadas. Contar el coste de las trazas externas. Primero definir un objetivo de mecanismo (convergencia, región o diversidad), luego elegir métricas primarias y tamaño de muestra. Ese ensayo se propone para después de la reunión.
""")

hyp=pd.DataFrame([
 ['H1 Fragmentación','Cada brazo recibe fracción de B y se inicializan tres poblaciones','Escalado sigue con sólo 40.83% medio para MOEA/D; individual usa 100%; uniforme equivale a unión de flujos cortos','Escalado mejora sin eliminar brazos; en 5×5 un individual alternativo gana','Respaldo descriptivo; causa parcial plausible','Igual total FE, cuotas fijas predefinidas, control del arranque y ablación de 2/3 brazos'],
 ['H2 Menor profundidad','Pausas y menor FE por brazo reducen refinamiento de subproblemas','Ventaja histórica MOEA/D persiste a 5000 FE; mejora al aumentar FE','Estado persiste; pausar no equivale a reiniciar; no hay control puro de profundidad','Plausible, no separada de H1','Replay con cuotas iguales y distinto orden, y MOEA/D al mismo FE que recibe en portafolio'],
 ['H3 Complementariedad insuficiente','La ganancia exclusiva no cubre el coste de dividir B','Unión histórica gana sólo .006493/.008617/.009547 con coste 3B; aportes MOEA/D predominan','NSGA-II/SPEA2 sí aportan MC positivo y hay bases donde ganan','Respaldo geométrico fuerte; eficacia presupuestaria no aislada','Ablaciones con igual FE total y cuotas de exploración mínimas predefinidas'],
 ['H4 Guía genética poco eficaz para HV','Diversidad genética puede no mejorar convergencia de volumen','Guía sube diversidad pero queda por debajo de MOEA/D; combinación sin ganancia adicional','Guía mejora al control original en 7/8 bases y AUC en 8/8','Efecto limitado observado; no inutilidad de cooperación','Registrar supervivencia, ganancia física e HV de hijos guiados frente a nativos con asignación común'],
 ['H5 Crédito inmediato incompleto','Beneficio futuro o donación se acredita al receptor o no recibe crédito','Recompensa global no registra ascendencia; archivos parciales no muestran aprendizaje oculto','Escalado simple ya mejora con el mismo crédito inmediato','Hipótesis sin contraste causal','Una variante aislada de crédito retardado/procedencia, con protocolo previo y coste igual'],
 ['H6 Explorar/explotar subóptimo','Bonos dominan recompensa cruda; revisitas aún cuestan FE','I2 aislada mejora 8/8 bases; términos reconstruidos y asignación cambian','No se demostró c,W óptimos; más explotación puede perder complementariedad','Evidencia del defecto de escala; óptimo desconocido','Analizar sensibilidad limitada en desarrollo y confirmar política congelada, sin usar test'],
 ['H7 Heterogeneidad de instancias','El mejor algoritmo y mecanismo dependen de rasgos y B','Excepción 5×5; perfiles históricos y pérdidas de guía en 10×10','MOEA/D gana 7/8 recientes; tamaño/perfil confundidos','Heterogeneidad observada; regla general pendiente','Bases replicadas por geometría, tratamientos cruzados y varios B por trayectoria']
],columns=['Hipótesis','Explicación','Evidencia favorable','Evidencia contraria / límite','Nivel de respaldo','Experimento necesario'])
hyp.to_csv(T/'hypotheses_evidence.csv',index=False,encoding='utf-8-sig')
put('22_por_que_no_supera_moead.md','Por qué el portafolio aún no supera a MOEA/D',f"""
**El hecho demostrado es una brecha de rendimiento bajo presupuesto total compartido. No hay una causa única demostrada.** En confirmación, HV medio MOEA/D=.951055 y escalado=.931368, diferencia −.019687. Escalado pierde frente a MOEA/D en siete de ocho medias de base; en 5×5 lo supera, pero allí SPEA2 es el mejor individual. La AUC también favorece a MOEA/D. Este resultado no implica superioridad universal en cualquier B o distribución.

{table(hyp)}

H1 y H2 están relacionadas y las métricas actuales no separan sus efectos. La cooperación de I1 sí aísla un cambio genético condicionado a una traza fija; la comparación entre escalado e individual cambia simultáneamente presencia de otros brazos y profundidad, de modo que no identifica una razón mecánica única. La ventaja de MOEA/D a 5000 FE históricos apoya estudiar profundidad y complementariedad, pero proviene de otra cohorte.

La evidencia más sólida de mecanismo es H6 a nivel de política: cambiar sólo la escala de explotación mejora SW-UCB manteniendo condiciones. No se ha identificado si su ventaja depende enteramente de asignar más FE a MOEA/D o también del orden y los retornos a otros brazos.

Para la reunión conviene decir: “hemos reducido la brecha del portafolio con una corrección de crédito, pero el beneficio complementario observado no demuestra aún compensación del presupuesto dividido”. Evitar “MOEA/D siempre es mejor”, “los otros brazos no sirven” y “el problema es únicamente fragmentación”.

Gráficas de apoyo: [01 calidad final](figures/01_hv_confirmacion.png), [03 progreso](figures/03_hv_fe.png), [05 cuotas](figures/05_asignacion.png), [13 presupuesto histórico](figures/13_presupuestos_historicos.png), [20 MC a distintos FE](figures/20_complementariedad_fe.png). Todas están explicadas y enlazadas a sus datos en el [catálogo de figuras](FIGURAS.md).
""")

put('23_eficiencia.md','Qué eficiencia está respaldada',f"""
Eficiencia significa calidad del conjunto de soluciones en relación con **evaluaciones y tiempo**, incluida la evolución durante la búsqueda. Una política más rápida con peor HV no es automáticamente más eficiente para el objetivo de tesis. Tampoco HV/FE final aislado describe la trayectoria.

| Dimensión | Resultado respaldado | Límite |
|---|---|---|
| Calidad a igual FE | Escalado mejora HV de SW-UCB original y uniforme a 3000 FE | Sigue debajo de MOEA/D en media |
| Calidad durante búsqueda | AUC escalado − original = +.014673; ocho bases favorables | AUC de individuales mayor en media; muestreo de 50 FE |
| Coste de tiempo | Escalado: +1.46% de tiempo medio, guía +4.59% | Sin desglose de overhead; pequeña base escalado +37.8% |
| Umbral pareado | Escalado alcanza HV final original en 22/24; FE truncada media 2062.5 | Dos censuras; umbral depende de control de cada semilla |
| Coste de cooperación | Evaluación de hijos incluida en FE nativas | Replay necesita control adicional; no es política autónoma de 3000 FE |
| Selección y archivo | Incluidos en tiempo de búsqueda medido | No hay cronómetros aislados para atribuir sus costes |

Hay una mejora de eficiencia **relativa al portafolio original**: mejor calidad con el mismo B y cambio temporal agregado pequeño, además de mejor calidad acumulada. No se demuestra dominancia sobre el mejor individual, que sigue ofreciendo mayor HV/AUC medios con tiempo similar. Las comparaciones de calidad por segundo dependen fuertemente del tamaño; conviene revisar cada base antes de decidir un compromiso operacional.

El tiempo por FE aumenta con operaciones, selección ambiental y tamaño de archivo; su correlación no identifica un coste puro del decodificador. Se conservan tiempos por bloque y por corrida. No se añade consumo energético de CPU: E es un objetivo del calendario industrial, distinto del coste energético de ejecutar el software.

Ver [tiempo y censura](13_eficiencia_computacional.md), {link('recent_summary')}, {link('threshold_baseline_final_hv')}. La comparación global de la campaña, los ensayos previos de reproducción y las FE de auditoría están separados de FE de búsqueda.
""")

put('24_adaptabilidad.md','Qué adaptabilidad está respaldada',"""
Conviene distinguir tres propiedades que requieren evidencias diferentes.

| Propiedad | Evidencia disponible | Conclusión |
|---|---|---|
| Adaptación dentro de una corrida | Ventana de recompensas, términos UCB, cambios de brazo y diferencias por etapa | Implementada y observada; el escalado mejora su utilidad frente al control |
| Adaptación entre instancias | Cuotas distintas, ganadores distintos y respuestas de perfiles | Heterogeneidad observada; no existe todavía una regla validada basada en rasgos |
| Generalización | Nuevas bases de confirmación del mismo generador y perfiles por tamaño | Confirmación interna limitada; test final y familias externas pendientes |

El reparto desigual no basta: se exige que cambiar la política produzca una mejora bajo controles. I2 ofrece esa evidencia frente a SW-UCB original, con las ocho bases favorables. La reconstrucción de recompensas respalda que el mecanismo usa progreso reciente. Aun así, no demuestra que seleccione el mejor brazo posible en cada etapa: ese oráculo exige contrafactuales que no se ejecutaron.

La primera base pequeña asigna recursos y tiene ganadores distintos; la mayor parte del resto favorece MOEA/D. La relación con características no es causal porque perfil y geometría se confunden en la campaña reciente. Las correlaciones históricas tampoco se mantienen necesariamente al cambiar B. Por eso “adaptativo” describe una regla dependiente de observaciones, no una garantía de generalización.

PH detecta disminución de una señal global, pero esa señal disminuye naturalmente al refinar el archivo y depende de los algoritmos ejecutados antes. Sus alarmas no prueban cambios reales de régimen ni identificación de un nuevo mejor brazo. El resultado negativo respalda una decisión de parsimonia y sugiere estudiar escala del crédito antes de añadir más detectores.

Ver [selección](17_analisis_adaptabilidad.md), [recompensas](18_analisis_recompensas.md), [presupuesto](19_asignacion_presupuesto.md). Mantener intacto el holdout final es necesario para una futura afirmación de generalización.
""")

put('25_relacion_objetivos_tesis.md','Relación con la pregunta y los objetivos de tesis',"""
La pregunta de investigación se puede sostener como el estudio de **cómo asignación y cooperación afectan la eficiencia y adaptabilidad de un portafolio MO-JSSP**, sin imponer que siempre gane al mejor constituyente.

| Objetivo | Trabajo y evidencia | Estado |
|---|---|---|
| Resolver Cmax, tardanza y energía | Representación común, decoder factible, archivos Pareto, controles individuales | Implementado; optimalidad global desconocida |
| Integrar algoritmos complementarios | Tres brazos pausables, archivos locales/global, MC y solapamiento | Integración y complementariedad observadas |
| Asignar FE inteligentemente | RR, SW-UCB, UCB1/PH y escalado; trazas y ablación I2 | Mejora interna de escala respaldada |
| Compartir información útil | Padre externo, replay y eventos trazables | Señal favorable condicionada; autonomía y crédito pendientes |
| Mejorar eficiencia | HV/AUC a igual FE, tiempo y umbrales con censura | Frente al portafolio original sí; frente a MOEA/D no |
| Adaptarse a instancias | Instancias perfiladas, variación de cuotas y análisis exploratorio | Falta confirmación factorial con bases replicadas |
| Validez y reproducibilidad | Datos preservados, fuente congelada reciente, hashes, semillas, análisis por base | Fuerte para campaña reciente; procedencia histórica parcial |

Los aportes científicos defendibles son: detectar y corregir una desproporción entre explotación y exploración; separar cooperación genética de agregación mediante control de asignación; cuantificar complementariedad con sustitutos preservados; identificar límites de PH y de combinar mecanismos; y diseñar una evaluación que no confunda variantes ni semillas con bases independientes.

La tesis gana precisión al registrar también resultados negativos: mayor diversidad no asegura mayor HV, unión de búsquedas completas no prueba ventaja presupuestaria y combinar mejoras no garantiza aditividad. La auditoría muestra qué preguntas necesitan nuevos controles y evita presentar como resuelta la generalización.

Una redefinición del objetivo hacia “superar siempre a MOEA/D” no está respaldada por los datos ni es necesaria para justificar el estudio. La decisión académica es acordar el alcance de la contribución y un experimento final acotado, con resultados favorables y desfavorables igualmente publicables.
""")

findings=[
 'UCB escalado mejora SW-UCB original en HV final y AUC en las ocho bases de confirmación interna a 3000 FE; ΔHV +0.020680, Holm .015625.',
 'El portafolio escalado aún tiene menor HV medio que MOEA/D: .931368 frente a .951055, y pierde en siete de ocho bases.',
 'SPEA2 gana la base 5×5 de confirmación; NSGA-II también supera allí a MOEA/D. No existe superioridad individual uniforme.',
 'Padre externo con replay mejora HV medio +.008539 y diversidad genética +11.84%, pero HV corregido p=.054688 y requiere una asignación externa.',
 'La combinación escalado + guía no añadió una mejora reproducible: ΔHV −.001742 frente a escalado en desarrollo; no se confirmó.',
 'La complementariedad geométrica es positiva y asimétrica; a 5000 FE/brazo MOEA/D aporta MC .030796 frente a .003065/.003849. La unión cuesta 15000 FE.',
 'Page-Hinkley C5 gasta 165 FE medias en resondeo y no acredita ventaja corregida frente a SW-UCB. Su comparación reutiliza los resultados de calibración C5.',
 'El inventario contiene 1336 instancias por contenido y 2746 copias; sólo una pequeña parte tiene comparaciones actuales. Holdout: 80 variantes de 16 bases, sin abrir para rendimiento.',
 'No puede afirmarse una regla general algoritmo–tamaño. La confirmación tiene 4 bases pequeñas, 1 mediana y 3 grandes; tamaño y perfil están confundidos.',
 'El ensayo histórico de cuello de botella favorece la ventaja relativa de NSGA-II en 8/8 bases, pero tras ocho contrastes Holm queda en .0625: es una hipótesis dirigida para confirmar.'
]
findtext='\n'.join(f'{i+1}. {x}' for i,x in enumerate(findings))
put('26_resumen_ejecutivo.md','Resumen ejecutivo para reunión del 16 de octubre',f"""
**Estado:** portafolio MO-JSSP implementado y evaluado; mejora interna reproducible del selector; superioridad sobre el mejor individual y generalización todavía no demostradas. Este es material de seguimiento, no una sustentación final. Extensión objetivo: tres páginas de lectura, sin figuras insertadas.

## Qué hay construido

MOEA/D, NSGA-II y SPEA2 comparten representación y evaluación de Cmax, tardanza y energía. El orquestador conserva estados y reparte bloques de FE. Se compararon uniforme, SW-UCB original, UCB1/PH, UCB escalado, padre externo con replay y combinación. El archivo global agrega soluciones y mide crédito; sólo las variantes de padre externo transfieren genotipos.

## Diez hallazgos

{findtext}

## Resultado principal comparable
{table(means,['Método','HV','AUC-HV','Tiempo (s)'],4)}

Ocho bases nuevas, tres semillas, 3000 FE. El tiempo de guía excluye obtener la traza control de 3000 FE adicional. Escalado cambia el reparto MOEA/D/NSGA-II/SPEA2 de 34.44/32.71/32.85% a 40.83/25.83/33.33%; tiempo medio +1.46%, diversidad genética +11.56%. No equivale a ganar al mejor individual.

## Validez y límites

Inferencia por base, semillas promediadas, bootstrap y pruebas exactas, familia principal de dos candidatos con Holm. La confirmación es del mismo generador y repite perfil asociado a tamaño. Los 450 cortes históricos son 150 trayectorias, y el piloto coincide en calidad con el primer corte. Los datos originales y algoritmos se preservan; esta auditoría no consumió FE de optimización. La recomputación de 312 HV/AUC/MC coincide a precisión numérica.

## Qué proponer a los directores

Conservar escalado como candidato, fijar eficiencia respecto al portafolio original y mantener MOEA/D como referencia. Acordar una ablación presupuestaria para H1/H2 y una hipótesis dirigida de cuello de botella, con bases independientes. Decidir si la cooperación debe demostrarse como política online o permanecer como ensayo de mecanismo. Definir familias de pruebas, mínimo efecto útil y condición de apertura del test final antes de nuevas corridas. No afinar con el holdout.

Lectura de apoyo: [guion](27_guion_reunion.md), [decisiones](29_decisiones_directores.md), [informe integral](INFORME_INTEGRAL_MOJSSP.md), [auditoría](30_auditoria_final.md).
""")

top=['01_hv_confirmacion','02_diferencias_pareadas','03_hv_fe','05_asignacion','06_contribuciones','07_frentes_proyecciones','09_hv_tamano','10_cooperacion_diversidad','11_escala_ucb','12_page_hinkley']
script_sections=[
 ('0:00–1:00','Problema y criterio científico','Minimizamos tres objetivos y buscamos asignación/cooperación útiles. No necesitamos afirmar victoria universal. Mostrar arquitectura Mermaid de documento 02.',None),
 ('1:00–2:00','Evolución y resultado negativo histórico','Separar F8, Fases 1/2 y PH. El detector no añadió una ventaja corregida; el resultado negativo motivó estudiar escala.','12_page_hinkley'),
 ('2:00–3:00','Problema de crédito y cambio aislado','Explicar la fórmula original y la nueva escala común, conservando ventana y bono. No llamarlo FRRMAB.','11_escala_ucb'),
 ('3:00–4:00','Qué cambia en la asignación','Comparar cuotas y señalar que desigualdad necesita validación de calidad. La mayoría de FE sigue repartida.','05_asignacion'),
 ('4:00–5:00','Comparación de calidad final','Mismo B, nuevas bases, tres semillas. MOEA/D mantiene mayor media; SPEA2 gana la menor base.','01_hv_confirmacion'),
 ('5:00–6:00','Evidencia del escalado','Ocho diferencias positivas; CI y Holm de dos candidatos. Guía pierde una base y queda marginal tras corrección.','02_diferencias_pareadas'),
 ('6:00–7:00','Calidad durante la búsqueda y eficiencia','AUC incorpora trayectoria; mejor que original, aún por debajo de individuales. Tiempo +1.46% medio y heterogeneidad por base.','03_hv_fe'),
 ('7:00–8:15','Complementariedad','Definir MC con recuperación de sustitutos. No sumar MC. Mostrar proyecciones opcionales si preguntan por regiones.','06_contribuciones'),
 ('8:15–9:15','Cooperación y combinación','Padre externo bajo replay aísla variación genética. Mayor diversidad no garantiza HV. Combinación sólo en desarrollo y sin ventaja adicional.','10_cooperacion_diversidad'),
 ('9:15–10:30','Características e instancias','Inventario amplio pero pocas bases evaluadas. Categorías descriptivas 4/1/3 y perfil confundido con tamaño. No hay regla de especialización general.','09_hv_tamano'),
 ('10:30–11:30','Regiones y presupuesto de la unión','La figura histórica ilustra diferencias de frentes; explicitar 3000 FE por brazo y 9000 FE de unión.','07_frentes_proyecciones'),
 ('11:30–13:30','Cinco decisiones y próximos controles','Discutir objetivo de tesis, retención de brazos, autonomía de guía, diseño por perfiles y protocolo final. Reservar preguntas y no abrir test.','')
]
put('27_guion_reunion.md','Guion técnico de 10 a 15 minutos',"""
Duración propuesta: 13 minutos 30 segundos más preguntas. Se usan diez gráficas y un diagrama de arquitectura. Para diez minutos, omitir proyecciones y condensar antecedentes; para quince, ampliar características con figuras 08/21 como respaldo. Los enlaces PNG están listos para mostrar y SVG para edición sin pérdida.

"""+'\n\n'.join('## '+time+' · '+title+'\n\n'+text+ ('\n\n[Gráfica '+f[:2]+']('+FIG[f]['png']+').' if f else '') for time,title,text,f in script_sections)+"""

## Frases que conviene usar

“Mejoramos de forma reproducible una limitación del portafolio, pero no hemos demostrado que supere al mejor algoritmo individual.” “Tenemos complementariedad observada; su utilidad bajo presupuesto compartido es otra pregunta.” “La guía tiene un efecto condicionado a la asignación reproducida, con el coste externo declarado.” “La relación con tamaño es exploratoria: hay pocas bases y perfiles confundidos.”

## Material de respaldo

Las 23 figuras y fuentes están en [FIGURAS.md](FIGURAS.md). Para estadísticas exactas consultar [12](12_analisis_estadistico.md), para hipótesis causales [22](22_por_que_no_supera_moead.md), para preservación y límites [30](30_auditoria_final.md). No presentar el test reservado ni uniones de 3B como portafolios de B.
""")

qa=[
('¿Por qué estos tres algoritmos?','Hecho: implementan tres mecanismos diferentes de selección: descomposición, ranking/crowding y fuerza/densidad. Interpretación: esa variedad hace razonable probar complementariedad. No garantiza que los tres deban mantenerse en el portafolio final.','03_catalogo_algoritmos_portafolios.md'),
('¿Qué aporta MOEA/D?','Hecho: mayor HV/AUC medio en confirmación y mayor MC histórico. Interpretación: es la referencia más fuerte de las evaluadas a estos presupuestos. No se ha demostrado superioridad universal.','16_contribuciones_por_brazo.md'),
('¿Qué aporta NSGA-II?','Hecho: existen victorias locales e históricas; su ventaja relativa aumenta con cuello de botella en ocho bases históricas. Interpretación: candidato para un ensayo dirigido, sin regla general confirmada tras multiplicidad.','09_rendimiento_por_caracteristicas.md'),
('¿Qué aporta SPEA2?','Hecho: gana la base 5×5 reciente y aporta volumen exclusivo en otras uniones. Interpretación: su menor media no justifica eliminarlo sin ablación presupuestaria.','14_complementariedad.md'),
('¿Cómo funciona el portafolio?','Hecho: conserva tres estados, selecciona un brazo y ejecuta bloques de 50 FE, une archivos y actualiza crédito global. La selección no reinicia las poblaciones.','02_arquitectura_portafolio.md'),
('¿Por qué se usa HV?','Hecho: mide el volumen dominado del frente aproximado respecto a una referencia fija. Interpretación: permite valorar conjuntos en los tres objetivos, pero depende de normalización/referencia y no describe toda la diversidad.','03_catalogo_algoritmos_portafolios.md'),
('¿Por qué AUC-HV?','Hecho: resume calidad durante las FE disponibles, no sólo al final. El informe integra por trapecios desde (0,0) y divide por B. Interpretación: ayuda a estudiar comportamiento anytime.','12_analisis_estadistico.md'),
('¿Qué significa eficiencia?','Hecho operacional: calidad a igual FE, trayectoria, tiempo y probabilidad de alcanzar umbrales. Interpretación: no basta ser rápido si el conjunto de soluciones empeora.','23_eficiencia.md'),
('¿Qué significa adaptabilidad?','Hecho: asignación depende de recompensas recientes y cambia durante la corrida. Interpretación: su utilidad necesita comparación controlada; generalizar a nuevas familias requiere otra evidencia.','24_adaptabilidad.md'),
('¿Qué demuestra UCB escalado?','Hecho: cambiar sólo la escala de explotación mejora HV/AUC de SW-UCB en 8/8 bases de confirmación; HV Holm .015625. No demuestra optimalidad de c/W ni victoria sobre MOEA/D.','17_analisis_adaptabilidad.md'),
('¿Cómo se seleccionan brazos?','Hecho: probes, media de ventana y bono UCB; ausentes de ventana tienen infinito; empates sembrados. Escalado divide la media por un máximo común reciente.','18_analisis_recompensas.md'),
('¿Qué demuestra la complementariedad?','Hecho: varios archivos aportan volumen que no cubren los otros. No demuestra beneficio a igual presupuesto ni especialización general por instancia.','14_complementariedad.md'),
('¿Qué significa contribución marginal?','Hecho: HV de unión menos HV de unión de los demás archivos completos. Hay que recuperar sustitutos antes dominados. No se suma como HV total.','16_contribuciones_por_brazo.md'),
('¿Por qué compartir soluciones?','Hipótesis: un genotipo ajeno puede aportar combinaciones que no alcanzó el receptor. Hecho: el replay produce señal positiva media con más diversidad, condicionada a esa asignación.','20_analisis_cooperacion.md'),
('¿Cómo se escoge el donante?','Hecho: extranjero, ausente del archivo local, más distante en objetivos normalizados por criterio maximin; se congela por bloque y sustituye segundo padre cada diez cruces elegibles.','20_analisis_cooperacion.md'),
('¿Se reutiliza gratis el fitness del hijo?','Hecho: no. Se comparte el genotipo padre y cada hijo se decodifica y evalúa nativamente, consumiendo FE. No equivale a insertar una solución evaluada en la población.','04_cambios_implementados.md'),
('¿Por qué no supera a MOEA/D?','Hecho: sigue una brecha de .019687 HV medio a 3000 FE. Hipótesis: fragmentación, profundidad, complementariedad insuficiente y crédito imperfecto. No hay un ensayo que identifique una causa única.','22_por_que_no_supera_moead.md'),
('¿Influye el tamaño?','Hecho: se observan diferencias y una excepción en 5×5. Interpretación: no puede separarse tamaño de perfil con una base por geometría reciente y una sola base mediana.','08_rendimiento_por_tamano.md'),
('¿Influyen los modos de velocidad?','Hecho: ofrecen intercambio tiempo–energía; los cinco modos están en todas las bases principales. No se puede estimar el efecto del número de modos sin variarlo en corridas comparables.','06_caracterizacion_instancias.md'),
('¿Cómo se controla FE?','Hecho: inicialización y cada evaluación de hijo consumen presupuesto; los 312 registros suman 3000 FE reales y 60 bloques. Las métricas offline no generan soluciones nuevas.','30_auditoria_final.md'),
('¿Qué validez tienen los resultados?','Hecho: controles internos, fuente reciente congelada, base como unidad, semillas comunes, archivos y recálculos. Límite: pocas bases, generador único, perfiles confundidos y test sin abrir.','12_analisis_estadistico.md'),
('¿Qué falta experimentar?','Recomendación: ablación de presupuesto/brazos y contraste dirigido de cuello de botella; luego cooperación autónoma si se prioriza. Requiere acuerdo de objetivo, efecto mínimo y protocolo de validación.','29_decisiones_directores.md'),
('¿Cuál es el aporte científico?','Interpretación apoyada: diagnóstico del crédito, ablación aislada de escala, cooperación controlada, MC correcto y resultados negativos trazables. La tesis no depende de inventar superioridad del portafolio.','25_relacion_objetivos_tesis.md'),
('¿Page-Hinkley funcionó?','Hecho: C5 no acreditó ventaja corregida; media 165 FE de resondeo. La comparación reutiliza sus corridas de calibración y no es confirmación independiente. No probar ventaja no prueba equivalencia.','01_evolucion_investigacion.md'),
('¿Qué significa un HV mayor que uno?','Hecho: referencia 1.1 en tres dimensiones permite hasta 1.331 en la caja ideal normalizada. HV >1 es compatible con la definición; no es un porcentaje de óptimo.','03_catalogo_algoritmos_portafolios.md'),
('¿Son 450 experimentos independientes?','Hecho: son cortes de 150 trayectorias históricas. Además, 1000/3000/5000 comparten historia, y las semillas repiten una misma base.','12_analisis_estadistico.md'),
('¿Cuántas instancias hay realmente?','Hecho: 2746 copias .dzn, 1336 contenidos distintos; el conjunto expandido tiene 200 variantes de 40 bases. El inventario incluye inválidos y archivos sin resultados comparables.','06_caracterizacion_instancias.md'),
('¿Se utilizó el test final?','Hecho: no se analizó rendimiento reservado ni se abrieron sus instancias para características detalladas. Sólo se conservaron hashes y metadatos declarados de 80 variantes/16 bases. Confirmación reciente es interna.','30_auditoria_final.md'),
('¿Compartir archivo es cooperación?','Hecho: una salida Pareto compartida puede ser unión pasiva; usarla para recompensa comunica crédito al selector. Sólo la guía transmite genotipos a variación. Son mecanismos diferentes.','02_arquitectura_portafolio.md'),
('¿Por qué más diversidad no implica más HV?','Hecho: distancia genética, rango y volumen exclusivo son métricas diferentes. Hipótesis: hijos distantes pueden no converger o aportar regiones pequeñas/redundantes. No se registró su destino completo.','15_espacio_objetivos.md'),
('¿Por qué no funcionó la combinación?','Hecho: ΔHV medio negativo con IC que incluye cero, 3/6 bases favorables; no se adoptó. Hipótesis: interacción de descendencia y crédito/asignación. No está causalmente identificada.','21_analisis_combinacion_mecanismos.md'),
('¿La mejora de guía es estadísticamente segura?','Hecho: HV Holm .054688, IC bootstrap positivo y 7/8 bases favorables. Interpretación: señal condicional prometedora, no confirmación fuerte al 5%; no seleccionar sólo el resultado más favorable.','12_analisis_estadistico.md'),
('¿La guía cuesta 3000 o 6000 FE?','Hecho: tratamiento 3000; control para obtener traza específica otras 3000. El par completo cuesta 6000 desde cero. No penalizar dos veces si la traza ya existe, pero declararla.','13_eficiencia_computacional.md'),
('¿Eliminarías NSGA-II o SPEA2?','Recomendación provisional: no por una media agregada. Medir ablaciones 2/3 brazos a igual B y múltiples bases. MC final no es efecto de reasignar FE tras eliminar un brazo.','29_decisiones_directores.md'),
('¿Una recompensa cero indica estancamiento definitivo?','Hecho: indica ausencia de ganancia global en ese bloque. Hubo recuperaciones después de ceros y el estado local puede mejorar sin superar el archivo global.','19_asignacion_presupuesto.md'),
('¿Las correlaciones permiten configurar el portafolio?','Hecho: son exploratorias y con n pequeño; tamaño/perfil están confundidos. Interpretación: sirven para diseñar hipótesis, no para un modelo de selección generalizado.','09_rendimiento_por_caracteristicas.md'),
('¿Qué cambió durante esta auditoría?','Hecho: sólo se crearon scripts, tablas, figuras y documentos en el directorio de reunión. No se cambiaron algoritmos, resultados históricos, ramas ni se hicieron push. Se contrastan hashes antes/después.','30_auditoria_final.md'),
('¿Conocemos el Pareto óptimo?','Hecho: no. Los archivos son aproximaciones observadas y las cotas son analíticas conservadoras. No se interpreta HV como porcentaje de óptimo conocido.','15_espacio_objetivos.md'),
('¿Es causal el efecto de los perfiles?','Hecho: las variantes históricas comparten base y permiten un contraste emparejado de la perturbación del generador. Límite: cambian instancia y normalización; no prueba un efecto universal del rasgo ni una causa de superioridad.','09_rendimiento_por_caracteristicas.md'),
('¿Qué se puede defender mañana?','Interpretación basada en evidencia: corrección reproducible del selector, complementariedad limitada y cooperación condicional, con una agenda concreta. La reunión debe acordar el siguiente contraste y el alcance final.','26_resumen_ejecutivo.md')
]
put('28_preguntas_respuestas.md','40 preguntas posibles y respuestas fundamentadas','\n\n'.join(f'## {i+1}. {q}\n\n{ans}\n\nEvidencia: [{src}]({src}).' for i,(q,ans,src) in enumerate(qa)))

decisions=pd.DataFrame([
 ['1. Criterio de éxito de tesis','Mejorar portafolio base / vencer mejor individual / compromiso multiindicador','Escalado mejora control; pierde media frente a MOEA/D','Objetivo centrado en mecanismos es verificable y permite resultados negativos','Cambiar criterio después de ver test induciría sesgo','Mantener eficiencia/adaptabilidad y MOEA/D como referencia fuerte','Acordar mínimo efecto relevante, restricciones y métrica primaria'],
 ['2. Composición y fragmentación','Tres brazos / MOEA-D+NSGA-II / MOEA-D+SPEA2 / control con cuotas fijas','MC asimétrico y ganadores locales; 40.83% FE medio a MOEA/D en escalado','Ablación a igual B separa utilidad presupuestaria','Eliminar por media puede perder 5×5 u otras regiones','Acordar una ablación pequeña con bases replicadas y mismas FE totales','Precisión/potencia por base y cuota mínima predefinida'],
 ['3. Alcance de cooperación','Ensayo de mecanismo con replay / política online / congelar línea por ahora','Guía positiva media, p corregida .054688; combinación no adicional','Replay aísla genética; online sirve como política deployable','Coste externo de replay y crédito cruzado sin genealogía completa','No vender replay como política autónoma; decidir si financiar una ablación de asignación común','Costes totales, supervivencia de hijos guiados, trazas comparables'],
 ['4. Hipótesis de especialización','Contraste dirigido de cuello de botella / factorial amplio / modelo predictivo','NSGA-II Δrel +.014506 en 8/8, Holm ocho pruebas .0625; una base por geometría','Contraste dirigido reduce preguntas y permite replicación estructural','Modelo complejo sobre ocho bases sobreajustaría','Priorizar cuello de botella con varias bases por geometría y efecto mínimo','Generación/split previo y potencia/IC objetivo; modos constantes no responden su efecto'],
 ['5. Validación final y multiplicidad','Nueva confirmación interna / abrir test final una vez / benchmark externo','Test intacto; confirmación actual mismo generador y confusión tamaño-perfil','Protocolo congelado sostiene generalización y trazabilidad','Abrir para afinar contamina la evaluación final','Congelar política y análisis antes de abrir test; decidir una única familia principal','Presupuesto acordado, bases/semillas, reglas de parada, hashes y plan para resultados negativos']
],columns=['Decisión','Alternativas','Evidencia','Ventajas','Riesgos','Recomendación provisional','Información adicional'])
decisions.to_csv(T/'directors_decisions.csv',index=False,encoding='utf-8-sig')
put('29_decisiones_directores.md','Cinco decisiones priorizadas para los directores',table(decisions)+"""
Estas decisiones no autorizan automáticamente nuevas campañas: esta tarea sólo prepara evidencia. Los experimentos propuestos deben ejecutarse después de acordar el diseño, con una hipótesis y cambio aislados. Antes de la reunión bastan el inventario, la corrección de afirmaciones históricas y la congelación del material; no es necesario abrir el test ni ajustar el portafolio.

La recomendación provisional común es conservar escalado como candidato de investigación, mantener el control original para ablación y usar MOEA/D como referencia explícita. Un resultado negativo de una ablación sigue siendo útil para delimitar el portafolio final.
""")

limitations=pd.DataFrame([
 ['Especialización general','Varias bases independientes por geometría/perfil y más cantidad de modos','Separar efectos confundidos y estimar variación entre bases','Diseño cruzado con hipótesis dirigida, semillas comunes y análisis por base','Después; acordar mañana'],
 ['Causa de brecha con MOEA/D','Ablaciones de composición, cuota y orden a igual FE','MC geométrico no reasigna FE ni controla profundidad','Cuotas/replay y 2/3 brazos, una mejora aislada','Después'],
 ['Guía autónoma','Tratamiento online con control de asignación y coste completo','El replay reutiliza una traza obtenida externamente','Ablación controlada; informar coste 2B cuando proceda','Después'],
 ['Crédito retardado y ascendencia','Genealogía completa y destino de hijos, incluidos descartados','Primera observación no identifica donación causal','Instrumentación futura congelada, luego una variante aislada','Después'],
 ['Diversidad genotípica histórica','Poblaciones o genotipos ausentes en archivos antiguos','Vectores objetivo no permiten reconstruir genomas','Declarar no disponible; sólo una reproducción autorizada generaría esos datos','No necesaria antes'],
 ['MC reciente continuo por FE','Archivos locales de todos los brazos por bloque','Milestones globales no reconstruyen sustitutos locales antiguos','Guardar snapshots futuros; no sustituir por suma ΔHV','Después'],
 ['Coste aislado de selector/archivo','Cronómetros separados bajo el mismo trabajo de búsqueda','Tiempo total mezcla operaciones y distintos archivos','Instrumentación de costes que no cambie RNG ni FE','Después'],
 ['Procedencia histórica exacta','Instantánea de fuentes cargadas y parámetros efectivos','Commit reportado puede omitir cambios sucios del experimento','Preservar metadata disponible y reconocer incertidumbre; no inventar hashes cargados','Documentado antes'],
 ['Generalización','Test final y familias no usadas para hipótesis','Confirmación actual comparte generador/perfiles','Protocolo congelado y apertura única de test, validación externa posterior','Después del acuerdo'],
 ['Unidad física energética y modelo ampliado','Documentación de unidades y energía ociosa si forma parte del problema','E implementada no es energía de CPU ni se ha validado una unidad kWh','Mantener definiciones actuales; consultar alcance académico','Discutir mañana'],
 ['Categoría mediana','Más de una base de 20×20 en cohorte reciente','IC entre bases no estimable con n=1','Replicar geometría y perfiles manteniendo grupos y FE','Después'],
 ['Archivos reservados e inválidos','Acceso autorizado a test sólo para final; errores de archivos inválidos documentados','Inventario no debe contaminar hipótesis ni esconder errores','Mantener metadatos reservados y estados explícitos','Ya aplicado']
],columns=['Pregunta pendiente','Qué falta','Por qué','Cómo obtenerlo / experimento','Momento'])
limitations.to_csv(T/'limitations_missing_information.csv',index=False,encoding='utf-8-sig')
put('31_limitaciones_y_pendientes.md','Limitaciones, datos ausentes y próximos experimentos',table(limitations)+"""
Las ausencias no se rellenan con estimaciones de otras campañas. Las propuestas no se ejecutaron en esta tarea. La prioridad para mañana es comunicar qué sí se sabe y acordar un contraste acotado; aumentar indefinidamente semillas de las mismas ocho bases no resuelve falta de diversidad estructural.

No se recomienda usar el archivo histórico sin split como nuevo test por conveniencia. Su historia de exposición no está clara. Si se usa, debe etiquetarse desarrollo/exploración hasta demostrar separación previa.
""")

# Final audit is assembled after the verifier; this paragraph declares current scope.
put('30_auditoria_final.md','Auditoría final y conservación de evidencia',f"""
## Cálculos verificados sin optimizar

Se recalcularon HV desde todos los frentes finales recientes, AUC desde bloques y MC desde los archivos locales completos. Se utilizó un algoritmo independiente de unión de cajas por barrido, sin alterar normalización ni referencia. El [registro numérico](evidence/analysis_audit.json) y {link('recent_metric_checks')} muestran:

| Control | Resultado |
|---|---|
| Corridas recientes | 312 |
| Error máximo HV final | {audit['max_hv_error']:.3g} |
| Error máximo AUC | {audit['max_auc_error']:.3g} |
| Error máximo MC | {audit['max_marginal_error']:.3g} |
| FE por corrida | Todas 3000, 60 bloques |
| FE de optimización nuevas | 0 |
| Rendimientos holdout utilizados | 0 |
| Características holdout | Sólo metadatos declarados; contenido reservado |

La caracterización vectorizada se comprobó independientemente con el lector de dominio en {link('independent_feature_checks')}; diferencia máxima 1.42×10⁻¹⁴. Los hashes originales y el estado Git anterior están en [preservación](evidence/preservation_before.json). La comprobación final de integridad se añade a [verification.json](evidence/verification.json), con diferencias explícitas si las hubiera. No se confunde la auditoría previa de 20131 calendarios con un recálculo de calendarios realizado hoy: ahora se verifican objetivos/frentes guardados, no se reejecutan algoritmos.

## Dependencias y fuentes

Piloto y corte de 1000 FE: 150 pares de HV idénticos. PH C5 calibración/comparación: 30 pares idénticos. Se conservan como cohortes distintas con dependencia declarada, sin sumar evidencia independiente. Los parámetros de semillas internas históricas difieren de la campaña reciente: Fase 2 portafolio usa (s×10007+17/29/43) mod (2³¹−1), individuales usan s; reciente alinea brazos s/s+1/s+2 también para controles individuales. Esto impide atribuir diferencias entre campañas sólo a mecanismos.

Los 50 archivos bajo `data/invalid` conservan errores de lectura documentados; no se infiere su causa ni que fueran intencionales. Los resultados antiguos no tienen todos un commit/código cargado exacto. La campaña reciente preserva instantáneas y una corrección de hashes de la línea base: no se oculta esa limitación mediante HEAD actual.

## Afirmaciones históricas revisadas

1. El cierre PH dice “superior” aunque sus tres contrastes Holm no son significativos: conservar SW-UCB por parsimonia es defendible; superioridad estadística no.
2. La Fase 1 utiliza expresiones de especialización causal/general con una base por geometría: este informe las rebaja a señales exploratorias.
3. La contribución heredada restaba puntos del ND ya filtrado: se usa la definición canónica recuperando sustitutos.
4. Un metadato histórico indica mutación .1, mientras los constructores usados y la instantánea reciente especifican .2 para secuencia y 1/N para modos: se explicita la incertidumbre histórica.
5. “Cotas dinámicas” en un documento PH no significa que el normalizador se reescale durante búsqueda: las cotas de instancia son fijas bajo la implementación auditada.

## Visualización, estadística y trazabilidad

Cada figura identifica cohorte, FE, instancias/semillas y tabla fuente. Para datos estructurales FE no aplica; para la unión se indica coste 3B. Los mapas no mezclan objetivos físicos de bases diferentes. Se revisan visualmente PNG, leyendas y escalas, con SVG para reutilización. La familia principal de dos pruebas es distinta de las exploratorias; cada tabla conserva unidad base. Las figuras 14 y 15 se ajustaron tras inspección para que las barras de color no oculten datos.

El [manifest de evidencia](evidence_manifest.json) enlaza archivos originales, transformaciones y hashes de productos. No se hizo checkout, commit, push ni modificación de algoritmos o resultados originales. Todo lo nuevo está en este directorio. No se instalaron paquetes: CSV/estadística principal usa el Python bundled; gráficos y estadísticas adicionales usan matplotlib/SciPy ya existentes, ausentes del bundle.
""")

# Integral report keeps all requested technical subjects, with specific evidence sections.
intro=f"""# Informe integral MO-JSSP para seguimiento con directores

Reunión: 16 de octubre de 2026. Corte de evidencia: auditoría del 15 de octubre. Trabajo exclusivamente de análisis y documentación, sin nuevas optimizaciones.

## Resumen

El resultado central es una mejora reproducible del portafolio mediante escalado del crédito UCB, con ΔHV +.020680 y AUC +.014673 frente al original en ocho bases de confirmación interna. El portafolio no supera al mejor individual en promedio. La guía genética produce una señal condicional positiva y mayor diversidad; su coste de replay y la multiplicidad limitan la afirmación. Combinar ambos mecanismos no añade ventaja demostrada. La caracterización amplia del archivo no subsana las pocas bases independientes de rendimiento ni la confusión tamaño/perfil.

## Contexto y objetivos

Se estudia cómo integrar MOEA/D, NSGA-II y SPEA2 para obtener aproximaciones no dominadas de Cmax, tardanza y energía bajo presupuesto FE. Eficiencia y adaptabilidad se evalúan con calidad, trayectoria, tiempo, contribuciones y asignación. La investigación prioriza evidencia reproducible y resultados negativos informativos. No tiene como condición fabricar una victoria del portafolio.

## Diez hallazgos principales

{findtext}

## Tabla de versiones
{vtable}

## Tabla de algoritmos por tamaño
{size_table}

Las categorías son terciles del diseño de ocho geometrías. Una base mediana no permite generalizar. [Tabla por instancia](tables/best_algorithm_by_instance.csv).

"""
selected=['02_arquitectura_portafolio.md','03_catalogo_algoritmos_portafolios.md','01_evolucion_investigacion.md','06_caracterizacion_instancias.md','07_clasificacion_tamanos.md','11_comparacion_standalones_portafolios.md','12_analisis_estadistico.md','09_rendimiento_por_caracteristicas.md','14_complementariedad.md','16_contribuciones_por_brazo.md','17_analisis_adaptabilidad.md','20_analisis_cooperacion.md','21_analisis_combinacion_mecanismos.md','23_eficiencia.md','24_adaptabilidad.md','22_por_que_no_supera_moead.md','25_relacion_objetivos_tesis.md','31_limitaciones_y_pendientes.md']
consolidated=intro
for n in selected:
 text=docs[n];lines=text.splitlines();consolidated+='\n\n## '+lines[0].removeprefix('# ')+'\n\n'+f'Capítulo específico: [{n}]({n}).\n\n'+'\n'.join(('##'+line if line.startswith('#') else line) for line in lines[2:])
consolidated+='\n\n## Discusión y conclusiones\n\n'+"""La complementariedad existe, pero su volumen exclusivo no prueba que compense el presupuesto repartido. La cooperación genética tiene efecto condicionado a asignación fija y no ha demostrado ser el mejor mecanismo online. La corrección de escala mejora eficiencia y utilidad adaptativa frente al portafolio original. El liderazgo medio de MOEA/D permanece y debe ser el control de referencia. Sus causas se mantienen como hipótesis separadas y contrastables.

La relación algoritmo–tipo de instancia es una pregunta abierta: los datos apoyan heterogeneidad y un ensayo dirigido de cuello de botella, no una taxonomía predictiva consolidada. La confirmación interna no reemplaza un test final reservado. No se debe ajustar con resultados de ese test ni presentar las variantes correlacionadas como nuevas bases.

## Trabajo futuro y decisiones

"""+table(decisions)+'\n\n## Referencias y procedencia\n\nVer [REFERENCIAS.md](REFERENCIAS.md), [inventario de campañas](tables/campaign_inventory.csv), [manifest](evidence_manifest.json) y [auditoría final](30_auditoria_final.md).'
(O/'INFORME_INTEGRAL_MOJSSP.md').write_text(consolidated,encoding='utf-8')

for n,text in docs.items():(O/n).write_text(text,encoding='utf-8')

(O/'FIGURAS.md').write_text('# Catálogo de las 23 figuras y sus fuentes\n\n**Diez para la reunión:** '+', '.join('['+n[:2]+']('+FIG[n]['png']+')' for n in top)+'.\n\n'+ '\n\n'.join('## '+f['id']+'\n\n'+fig(f['id'])+'\n[Versión vectorial SVG]('+f['svg']+').' for f in figmeta),encoding='utf-8')
(O/'REFERENCIAS.md').write_text("""# Referencias y jerarquía de evidencia

La evidencia empírica procede de archivos locales, preservados por SHA-256. Las publicaciones siguientes fundamentan mecanismos; no prueban la eficacia en estas instancias. Se consultaron fuentes primarias o registros de los autores/editoriales. Consulta: 15 de octubre de 2026.

1. Zhang y Li (2007). [MOEA/D: A Multiobjective Evolutionary Algorithm Based on Decomposition](https://doi.org/10.1109/TEVC.2007.892759). Descomposición de objetivos y cooperación entre subproblemas dentro de MOEA/D; distinta de cooperación entre algoritmos del portafolio.
2. Deb, Pratap, Agarwal y Meyarivan (2002). [A fast and elitist multiobjective genetic algorithm: NSGA-II](https://doi.org/10.1109/4235.996017). Ranking, elitismo y crowding. [Registro institucional de los autores](https://research.birmingham.ac.uk/en/publications/a-fast-and-elitist-multi-objective-genetic-algorithm-nsga-ii).
3. Zitzler, Laumanns y Thiele (2001). [SPEA2: Improving the Strength Pareto Evolutionary Algorithm, TIK Report 103](https://sop.tik.ee.ethz.ch/publicationlistfiles/zlt2001a.pdf). Fuerza, densidad y archivo ambiental; sustenta el catálogo, no una garantía de especialización.
4. Li, Fialho, Kwong y Zhang (2014). [Adaptive Operator Selection With Bandits for a Multiobjective Evolutionary Algorithm Based on Decomposition](https://colalab.ai/publications/LiFKZ14.pdf), DOI 10.1109/TEVC.2013.2239648. Ventana, crédito dependiente de escala y selección de operadores. El escalado del repositorio no reproduce FRRMAB, y aquí los brazos son algoritmos completos.

Las fórmulas efectivamente usadas se verifican en código y snapshots, no se sustituyen por las formulaciones de los artículos. El signo de Page-Hinkley se toma de la especificación corregida y `change_detection.py` del repositorio original. Las pruebas y criterios de cierre se distinguen entre el protocolo reciente prospectivo y análisis exploratorios de esta auditoría.

Fuentes locales principales:

- [Campaña reciente y configuración](../portfolio_loop_20261015/manifest.json), [protocolo](../portfolio_loop_20261015/protocol.md), [procedencia corregida](../portfolio_loop_20261015/baseline_execution_provenance.json).
- [Fase 2 piloto](../expanded_portfolio_phase2/pilot/pilot_config.json), [diagnóstico presupuestario](../expanded_portfolio_phase2/budget_diagnostic/budget_config.json).
- Los resultados Fase 1, benchmark, PH y las instancias históricas del repositorio original se identifican mediante rutas absolutas y hashes en [preservación](evidence/preservation_before.json) y tablas con `source_file`. Se consultan sólo en lectura.
- [Dependencias entre campañas](evidence/cross_campaign_audit.json), [errores de recálculo](evidence/analysis_audit.json), [fuentes de figuras](figures/figure_manifest.json).
""",encoding='utf-8')

index='# Reunión MO-JSSP · 16 de octubre de 2026\n\n'+"""Empezar por [resumen ejecutivo](26_resumen_ejecutivo.md), [guion de 13 minutos](27_guion_reunion.md) y [cinco decisiones](29_decisiones_directores.md). El [informe integral](INFORME_INTEGRAL_MOJSSP.md) consolida la discusión técnica. Las conclusiones diferencian hechos, interpretaciones e hipótesis.

## Hallazgos principales

"""+findtext+'\n\n## Diez gráficas para explicar el proyecto\n\n'+'\n'.join('- ['+FIG[n]['title']+']('+FIG[n]['png']+')' for n in top)+'\n\n## Versiones del portafolio\n'+vtable+'\n\n## Algoritmos por tamaño (confirmación, 3000 FE)\n'+size_table+'\n\n## Entregables por fase\n\n'
for n in sorted(docs):index+='- ['+n+']('+n+')\n'
index+='- [05_inventario_instancias.csv](05_inventario_instancias.csv)\n- [Catálogo de figuras](FIGURAS.md)\n- [Referencias](REFERENCIAS.md)\n- [Manifest de evidencia](evidence_manifest.json)\n\n## Tablas procesadas\n\n'
for p in sorted(T.glob('*.csv')):index+='- ['+p.name+'](tables/'+p.name+')\n'
index+='\n## Reproducción del análisis\n\nLos scripts están en [scripts](scripts/README.md). No ejecutar los runners de optimización antiguos para regenerar este informe. La preservación inicial se captura una sola vez; el verificador final compara hashes sin tocar los originales.\n'
(O/'INDICE.md').write_text(index,encoding='utf-8')
(O/'scripts/README.md').write_text("""# Reproducción de la auditoría

Todos los scripts confinan escrituras a su directorio padre de reunión. Los datos originales son sólo lectura. No inicializan algoritmos ni ejecutan búsqueda. La primera captura `preserve.py` se niega a sobrescribir `preservation_before.json`.

Orden:

1. `preserve.py` con Python bundled (ya capturado; no sobrescribir).
2. `discover.py` con Python bundled: inventario de esquemas/configuración histórica.
3. `analyze.py` con Python bundled: inventario, características, tablas, HV/AUC/MC y estadística principal (NumPy/Pandas). Cambia sólo tablas derivadas.
4. `supplement.py` con Python existente con SciPy: contrastes exploratorios, dependencias e inspección independiente de características.
5. `plot.py` con Python existente con matplotlib: 23 figuras PNG/SVG desde tablas procesadas.
6. `report.py` con Python bundled: documentos y capítulos del informe.
7. `verify.py` con Python bundled: conservación, trazabilidad, enlaces y manifest final.

Python bundled: `C:/Users/lenin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. El Python 3.12 existente del sistema dispone de matplotlib/SciPy, que no están en el bundle. No se instalaron ni modificaron dependencias. Semilla de análisis 20261016; 20000 remuestreos bootstrap de bases. Las variaciones mínimas de IC frente al informe previo responden a la semilla analítica, no a cambios en datos.

Para una reproducción externa se requieren los archivos del manifest en las mismas ubicaciones o adaptar explícitamente ROOT/ORIGINAL en una copia de estos scripts. No interpretar un commit histórico como captura exacta de un árbol sucio. No interpretar CSV del test ni abrir sus instancias para hipótesis.
""",encoding='utf-8')
print('Created',len(docs),'chapter documents, integral report, executive pack, figure catalog and index.')
