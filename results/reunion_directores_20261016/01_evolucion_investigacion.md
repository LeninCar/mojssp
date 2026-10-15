# Evolución técnica y experimental

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

| Versión | Selección / asignación | Información compartida | Evidencia | Estado |
| --- | --- | --- | --- | --- |
| Histórico NSGA-II/MOPSO/NSGA-II+LS | SW-UCB y uniforme; brazos anteriores | Unión pasiva; búsqueda local sólo dentro de su brazo | 500/1000 FE; campañas F8 | Antecedente; no mezclar con los tres brazos actuales |
| MOEA/D, NSGA-II, SPEA2 individuales | Un brazo usa todo B | Sin intercambio | 1000, 3000, 5000; reciente 3000 | Controles vigentes |
| Uniforme RR | Bloques cíclicos de 50 FE | Archivo global como salida | Fase 2 y reciente | Control de fragmentación y agregación |
| SW-UCB original | Media ΔHV + bono; W=10,c=.07 | Archivo global mide recompensa; sin padre externo | Fase 2, PH y reciente | Línea base conservada |
| UCB1 acumulativo | Media de todas las recompensas + bono | Sin transferencia genética | PH: 5000 FE, 10 bases × 3 semillas | Control de olvido |
| UCB1 + Page-Hinkley C5 | Alarma reinicia crédito; δ=.0005, λ=.020 | Poblaciones y archivo se conservan | 270 calibración + 90 comparación, 5000 FE | No adoptado; sin ventaja corregida |
| UCB escalado | Media ΔHV / máximo reciente + mismo bono | Sin cooperación genética | 6 desarrollo y 8 confirmación, 3000 FE | Mejora reproducible frente a SW-UCB |
| Padre externo con replay | Copia exactamente la asignación del control SW-UCB | Un padre extranjero cada 10 cruces elegibles | 6 desarrollo y 8 confirmación, 3000 FE tratamiento | Evidencia condicional; coste del control adicional |
| Escalado + padre externo | Decisiones online con crédito escalado | Mismo mecanismo de padre externo | Sólo 6 desarrollo × 3 semillas, 3000 FE | No adoptado; sin ganancia adicional clara |
| SW-UCB c=.01/.03 (P5 paralelo) | Reducir el bono sin escalar crédito | Unión pasiva | 2 bases × una semilla; 1000 FE | Sensibilidad exploratoria; ver apéndice 32 |
| Inyección acotada P6/P7 paralela | SW-UCB c=.01 y secuencia fija | Hasta 2 incumbentes evaluados por bloque desde índice 6 | P6: 2 bases × una semilla; P7 parcial 1000 FE | Distinta de padre externo; corte externo separado |

## Qué cambió en la interpretación

El escalado mejora SW-UCB original en las ocho bases de confirmación, pero sigue debajo de MOEA/D en promedio. La cooperación tiene una señal favorable bajo asignación controlada; no constituye aún una política autónoma que incluya el coste de obtener esa asignación. Combinarla con escalado no produjo una ganancia adicional reproducible en desarrollo. El cierre actual es una mejora de un portafolio limitado, sin victoria general sobre sus componentes.

Fuentes: [campaign_inventory](tables/campaign_inventory.csv), [historical_summary](tables/historical_summary.csv), [recent_paired_statistics](tables/recent_paired_statistics.csv), [auditoría de dependencias](evidence/cross_campaign_audit.json). Los enlaces a tablas remiten a transformaciones reproducibles. Cada fila conserva campaña y fuente cuando corresponde. La relación completa de rutas, tamaños y SHA-256 originales está en [preservation_before.json](evidence/preservation_before.json). No se han ejecutado nuevas optimizaciones. Las inferencias son internas al generador y a las bases observadas; el test final permanece reservado.


## Línea paralela y estado externo

Existe además una línea P5/P6 de sensibilidad de c e inyección directa de incumbentes, distinta del padre externo. P7 seguía produciendo resultados durante la auditoría. Se documenta en [apéndice 32](32_linea_paralela_P5_P6_P7.md), con un corte parcial fijo, sin mezclar presupuestos ni incorporarlo como confirmación. El conteo de instancias corresponde al inicio: desapareció externamente `mojssp-dmab - copia`, mientras el repositorio original `mojssp-dmab` y este checkout conservaron su estado. Véase [preservación](00_preservacion_trazabilidad.md).
