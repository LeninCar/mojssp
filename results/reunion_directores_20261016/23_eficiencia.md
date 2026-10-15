# Qué eficiencia está respaldada

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

Ver [tiempo y censura](13_eficiencia_computacional.md), [recent_summary](tables/recent_summary.csv), [threshold_baseline_final_hv](tables/threshold_baseline_final_hv.csv). La comparación global de la campaña, los ensayos previos de reproducción y las FE de auditoría están separados de FE de búsqueda.
