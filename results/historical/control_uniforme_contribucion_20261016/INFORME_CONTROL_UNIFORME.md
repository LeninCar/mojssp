# Control uniforme de contribución marginal — MO-JSSP

## Respuestas principales

1. **Sí, la recomendación cambia al igualar el presupuesto:** 14 de 18 parejas
   cambian de máximo MC; cuatro conservan el mismo brazo. No hay empates numéricos
   del máximo. Seis bases y tres repeticiones por base, no 18 instancias independientes.
2. **NSGA-II y SPEA2 pueden ser máximos contribuyentes a igual presupuesto:**
   con 1000 FE cada uno, MOEA/D, NSGA-II y SPEA2 reciben seis recomendaciones
   cada uno. Este equilibrio es observado, no fue impuesto ni usado para seleccionar casos.
3. **La coincidencia MC–FE de scaled se interpreta como atribución condicionada
   a las oportunidades realizadas.** Solo cuatro líderes uniformes coinciden con
   el brazo de máximo FE escalado. Ello respalda que el máximo MC es sensible a
   la política y no es una etiqueta intrínseca de habilidad. No identifica por sí
   solo un efecto causal aislado de cada FE o de cada brazo.
4. **Hay utilidad complementaria de los tres algoritmos bajo oportunidades iguales,**
   pero no superioridad universal, cooperación activa demostrada ni selección óptima
   de brazos. La asignación uniforme reduce ceros de MC, mientras scaled obtiene
   mayor HV en 17/18 corridas y en las seis medias por base. Más brazos útiles
   marginalmente no equivale a un mejor frente global.
5. **Para una conclusión causal más específica faltan controles de asignación/replay,
   prefijos locales completos a cortes comunes, más semillas/bases y un criterio
   externo de relevancia práctica.** No faltan archivos para esta comparación final:
   las 18 parejas actuales son reconstruibles.

No se ejecutaron nuevas FE, ni se modificaron algoritmos, selector o recomendador.
El holdout permanece cerrado. No se usaron resultados de confirmación.

## Disponibilidad y comparabilidad

Se reutilizan las seis instancias development_00_5x5, development_01_10x10,
development_02_20x10, development_03_10x20, development_04_20x20 y
development_05_30x20, con semillas nominales 42, 43 y 44. Identidad comprobada
por SHA-256 frente al manifest de la campaña portfolio_loop_20261015.

Por pareja existen scaled.json, uniform.json y tres JSON standalone. La corrida
uniforme real tiene 60 bloques de 50 FE en orden round-robin y asigna exactamente
1000 FE a cada brazo; total 3000. Sus 54 archivos locales completos coinciden
con los milestones.1000 de los tres standalones, comparando cada genotipo,
objetivos y coordenadas normalizadas. La unión standalone no es una segunda
ejecución de control ni una observación adicional: verifica el mismo control
uniforme. El máximo configurado del brazo sigue siendo 3000 FE; se analiza su
prefijo a 1000, coincidente con el brazo del portafolio uniforme.

Ambas políticas usan población 30, mismos operadores y mapeo de RNG: MOEA/D n,
NSGA-II n+1 y SPEA2 n+2. Se conservan decoder, evaluator, dominancia, normalización
analítica y referencia (1.1,1.1,1.1). Los arm FE de scaled van de 300 a 2350.
No hay eventos de guía, donantes ni cruces dirigidos en estas políticas.

**Salvedad de versiones:** uniforme y standalone son del proceso baseline;
scaled corresponde a research_v1. No se afirma byte-identidad de ejecutables.
El archivo baseline_execution_provenance.json corrige sus hashes de módulos
cargados: los source_sha256 raw se tomaron del disco después de la carga.
Se verifican esos hashes contra code/baseline y los scaled contra research_v1.
Comparando AST de 32 módulos, solo arms.py, moead.py y spea2.py difieren por
hooks opt-in: herencia, reset de guía a None y envoltura del padre. Al retirar
esos hooks INACTIVOS en memoria, los AST coinciden. La guía está desactivada y
devuelve el padre nativo sin evaluación ni RNG adicionales. El chequeo no modifica
ningún archivo. Esta evidencia respalda comparabilidad funcional de la búsqueda
pasiva y declara la revisión; no sustituye un ensayo nuevo con un mismo build.

Los controles históricos phase2_budget son otras diez instancias, commit a5566d4,
presupuestos totales 1000/3000/5000 y se excluyen: ningún ID coincide con el piloto.
Solo se inspeccionan sus metadatos de desarrollo. No se cargan sus frentes para
rellenar parejas. control_inventory.csv distingue control real, unión de prefijos
y antecedentes no comparables.

## Cálculo y validación de MC

`P = ND(unión de archivos locales retenidos)` y
`MC(a)=HV(P)−HV(ND(unión de archivos de los otros brazos))`.

No se infiere MC de HV escalares. Se usan todos los objetivos/genotipos locales,
incluidos los dominados globalmente que pueden reaparecer al retirar un brazo.
Genotipos compartidos se conservan si queda otro propietario; vectores iguales
cuentan una vez para HV y los genotipos conservan trazabilidad. Se verifican
IDs, normalización analítica, ND, igualdad del frente global almacenado y unión,
y cotas `−ε≤MC≤HV_global+ε`, con ε=max(1e−12,1e−10×|HV_global|).

Se contrasta HV con una integración independiente de cajas 3D y con la función
nativa. Diferencias de orden flotante se interpretan con ε. Los valores uniformes
de HV/MC concuerdan con los campos raw; scaled reproduce las 18 recomendaciones
y 54 MC anteriores. La unión standalone reproduce HV, genotipos y las tres MC
del uniforme en todas las parejas. No hay procedencia global incierta ni compartida
entre brazos en estos frentes finales. No se infiere primer descubrimiento ni
ascendencia a partir de pertenencia al archivo retenido.

El contrafactual de MC es geométrico con archivos fijos; no es la trayectoria que
ocurriría al eliminar un brazo y redistribuir su presupuesto. Tampoco se suman MC
como si fueran el HV global. Las pruebas sintéticas cubren volumen analítico,
resurrección de puntos dominados, compartición, duplicados y rechazo de atribución
desconocida. Evaluator.evaluate está bloqueado durante análisis y pruebas.

## Comparación pareada y estabilidad

| base_id | changed_winner_count | scaled_winners | uniform_winners | hv_scaled_minus_uniform_mean |
| --- | --- | --- | --- | --- |
| development_00_5x5 | 0 | NSGA-II;MOEA/D;SPEA2 | NSGA-II;MOEA/D;SPEA2 | 0.012788 |
| development_01_10x10 | 2 | SPEA2;NSGA-II;MOEA/D | MOEA/D;MOEA/D;MOEA/D | 0.044340 |
| development_02_20x10 | 3 | MOEA/D;NSGA-II;MOEA/D | NSGA-II;MOEA/D;NSGA-II | 0.039689 |
| development_03_10x20 | 3 | SPEA2;NSGA-II;MOEA/D | NSGA-II;SPEA2;NSGA-II | 0.030023 |
| development_04_20x20 | 3 | NSGA-II;NSGA-II;MOEA/D | MOEA/D;SPEA2;SPEA2 | 0.034103 |
| development_05_30x20 | 3 | NSGA-II;MOEA/D;MOEA/D | SPEA2;NSGA-II;SPEA2 | 0.027179 |

El orden de ganadores en cada celda es semillas 42;43;44. Solo development_01_10x10
conserva un único líder uniforme (MOEA/D) en las tres repeticiones; las otras cinco
bases cambian. Scaled cambia en las seis. Tres observaciones iguales no confirman
estabilidad poblacional. stability_by_base_arm.csv informa frecuencias y MC media,
SD muestral, mediana y rango por base/política/brazo, junto a variación del HV.

| Propiedad descriptiva | UCB escalado | Uniforme |
| --- | --- | --- |
| Máximos MC: MOEA/D / NSGA-II / SPEA2 | 8 / 7 / 3 | 6 / 6 / 6 |
| MC nula entre 54 brazos-corrida | 34 | 6 |
| Corridas con 1 / 2 / 3 MC positivas | 16 / 2 / 0 | 0 / 6 / 12 |
| Bases con igual líder en sus 3 semillas | 0 | 1 |
| Acuerdo con ganador standalone a 3000 FE | 10/18 | 5/18 |

El último renglón es secundario y no mide corrección de MC. El standalone a 3000
recibe todo ese presupuesto; el brazo uniforme recibe 1000. Se conserva aparte
la comparación con el ranking individual a 1000 FE, identificando ambos horizontes.
No se selecciona política o regla por maximizar esas coincidencias.

![Cambios de líder](figures/02_winner_transitions.png)

Figura 2. Transición del máximo MC entre políticas, mismo caso/semilla. No es una
matriz de clasificación correcta/incorrecta. Desarrollo, seis bases × tres semillas,
3000 FE, referencia (1.1,1.1,1.1). Fuente: paired_policies.csv.

Los márgenes uniformes son menores: 0.0054%–4.0015% del HV global,
mediana 0.882%. Scaled mantiene 5.54%–15.38%.
El menor uniforme es development_04_20x20/43: SPEA2 supera a MOEA/D por apenas
0.00004497 de HV, aproximadamente 0.00538% del HV global. Es máximo numéricamente
único, pero no debe presentarse como ventaja práctica demostrada. Se reutiliza
la misma cuadrícula de sensibilidad de la auditoría previa (0,0.1,0.5,1,2.5,5,10,
15,20%); no se ajustó un umbral. Ningún margen uniforme supera el escenario de 5%.

![Márgenes](figures/04_margins_log.png)

Figura 4. Separación relativa del primero y segundo por base/semilla, escala
logarítmica. Fuente: policy_runs.csv. Las tres semillas están anidadas en una base.

## Calidad global frente a complementariedad

Scaled supera en HV a uniforme en 17/18 parejas; uniforme gana únicamente en
development_00_5x5/44 (1.041520 frente a 1.038350). Esa pareja conserva SPEA2 como
máximo contribuyente. Las seis diferencias medias por base favorecen scaled.
La media con peso igual por base es 0.031354 HV
(SD entre las seis diferencias medias: 0.011042). Son
resúmenes del piloto, sin significación general afirmada ni 18 unidades independientes.
Las instancias tienen límites distintos; la media de HV normalizado describe
este conjunto y no es una utilidad universal que sustituya las seis filas.

Uniforme conserva más brazos con aporte marginal final. Por ejemplo en
development_00_5x5/42, MC uniforme de MOEA/D≈0.005982, NSGA-II≈0.048800 y
SPEA2≈0.001468. En development_03_10x20/43, SPEA2 aporta≈0.021441 y MOEA/D≈0.017831,
con NSGA-II≈0.000067. En cambio, más profundidad asignada a un brazo puede generar
puntos que cubran regiones antes exclusivas de otros. La geometría final respalda
la pérdida de exclusividad; no se reconstruye la secuencia temporal exacta de
sustituciones. MC cero no prueba ausencia de utilidad pasada o potencial.

![Calidad pareada](figures/03_paired_hv_differences.png)

Figura 3. Diferencia HV scaled−uniform por semilla y media por base; sin tratar
semillas como instancias. Fuente: paired_policies.csv y paired_effects_by_base.csv.

## Interpretación de MC–FE y límites causales

Con igual FE hay máximos MC distintos, incluidos NSGA-II y SPEA2: los resultados
no se reducen a una jerarquía universal de MOEA/D. A la vez, 14 de los 18 líderes
uniformes recibieron menos oportunidades que el líder scaled. Eso muestra que
la interpretación del máximo MC cambia con las oportunidades realizadas y la
profundidad disponible; no permite llamar «error» a la asignación scaled, que
obtuvo mayor HV global en casi todas las parejas.

En scaled, FE y MC están asociadas descriptivamente dentro de cada base; los
coeficientes Spearman se calculan sobre nueve celdas brazo/semilla dependientes,
sin p-valores ni inferencia. En uniforme FE=1000 es constante: la correlación no
es estimable, no es cero. No se usa FE como criterio de recomendación.

No hay migración, padres externos u otro mecanismo activo de cooperación que
distinga estas dos políticas. Archivo global compartido aquí agrega resultados;
los brazos evolucionan con sus estados y RNG locales. La identidad completa de
archivos uniformes y prefijos standalone respalda esa independencia a 1000 FE.
Los controles de versión y de hooks reducen explicaciones por implementación,
pero no autorizan a atribuir un efecto causal aislado a «una FE adicional» de
un brazo: la intervención conjunta cambia política, vector completo de FE,
intercalado y feedback. Tampoco identifica el efecto de presupuesto separado
de la trayectoria estocástica para poblaciones de instancias no observadas.

**Se puede afirmar:** utilidad marginal condicionada al archivo y política,
complementariedad positiva bajo igualdad de FE y sensibilidad del líder al reparto.
**No se puede afirmar:** mejor algoritmo intrínseco/universal, generalización,
superioridad de uniforme, que MC máxima valide el selector, ni que el máximo FE
sea causa única del máximo MC. MC es atribución retrospectiva, no selección temprana.

## Datos faltantes y próximos controles, sin ejecutar

No falta ninguna de las 18 parejas para el análisis actual. Para separar mecanismos:

- Comparar políticas en un mismo build congelado y conservar todas las trazas;
  la equivalencia estática actual no reemplaza ese control de ejecución.
- Variar de manera cruzada/preregistrada los vectores de presupuesto con total
  fijo 3000 y flujos nativos pareados, incluyendo permutaciones entre brazos.
- Utilizar replay de asignaciones y archivos completos por cortes comunes para
  separar feedback del selector de profundidad de búsqueda y reconstruir MC(t).
- Aumentar semillas y bases de desarrollo sin elegir únicamente cambios favorables;
  fijar tamaño de muestra y análisis por base antes de cualquier confirmación.
- Definir externamente qué diferencia de HV justifica una recomendación concluyente,
  especialmente por los pequeños márgenes uniformes.

Nada de esto se implementa ni ejecuta en esta tarea. El archivo
limitations_and_missing_data.csv explica disponibilidad, consecuencia y siguiente
paso por pregunta. No se abre el holdout para elegir diseños o umbrales.

## Integridad y reproducción

Se preservan fuentes y los 101 productos de las dos auditorías anteriores,
verificados por hash antes y después. Las 18 corridas scaled reproducen el
resultado anterior y el selector reproduce 1026 decisiones desde feedback guardado;
uniforme reproduce el orden round-robin y los 54 archivos standalone completos.
HV y MC se contrastan con función nativa e integración independiente. No se vuelve
a ejecutar ninguna búsqueda ni se afirma una igualdad de rerun no realizado.

Para reproducir, copiar scripts/ de esta auditoría a scripts/ de un NUEVO
directorio directamente bajo results/ y ejecutar analyze.py y report.py en ese
orden con Python -B -X utf8; no copiar las salidas, que son de creación exclusiva.
Los scripts importan las funciones puras de la auditoría de solidez conservada;
su archivo se identifica en el manifiesto de entradas. Requieren numpy, pandas,
scipy y matplotlib. Para repetir la certificación, ejecutar también certify.py.
Las fuentes, tablas y figuras quedan enlazadas en INDICE.md.

**Dictamen:** conservar ambas políticas como contraste metodológico. UCB escalado
presenta mejor calidad global en este piloto; uniforme revela aportes complementarios
de los tres brazos con oportunidades iguales. La recomendación por MC debe continuar
etiquetada por política, presupuesto, instancia, semilla y margen, sin reinterpretarla
como ranking universal de algoritmos. Se detiene para revisión.
