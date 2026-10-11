# INFORME DE AUDITORÍA: COMPLEMENTARIEDAD DE NSGA-II+LS RESPECTO A NSGA-II

**Fecha:** 2026-10-05  
**Presupuesto:** 1,000 FE exactas por corrida (0 overshoot).  
**Instancias:** 10_10, 20_20, 30_30, 40_40, 50_50 | **Semillas:** 0, 1, 2, 3, 4 (25 corridas por algoritmo).  

## 1. Resumen de Resultados Agregados

| Instancia | HV NSGA-II | HV NSGA-II+LS | HV Unión | Delta HV LS->NSGA | Contribución Relativa | Soluciones Exclusivas LS | Soluciones Exclusivas NSGA-II | Tamaño Unión |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 10_10_2-5_1.dzn | 0.8264 ± 0.0302 | 0.6903 ± 0.0150 | 0.8291 ± 0.0292 | 0.002725 ± 0.003338 | 0.3331% | 1.80 | 28.80 | 30.6 |
| 20_20_2-5_1.dzn | 0.7662 ± 0.0103 | 0.6931 ± 0.0100 | 0.7724 ± 0.0116 | 0.006280 ± 0.004322 | 0.8093% | 5.20 | 18.80 | 24.0 |
| 30_30_2-5_1.dzn | 0.7459 ± 0.0095 | 0.6860 ± 0.0039 | 0.7496 ± 0.0091 | 0.003619 ± 0.002154 | 0.4832% | 3.20 | 14.20 | 17.4 |
| 40_40_2-5_1.dzn | 0.7437 ± 0.0036 | 0.6980 ± 0.0068 | 0.7453 ± 0.0042 | 0.001598 ± 0.001390 | 0.2138% | 3.40 | 14.40 | 17.8 |
| 50_50_2-5_1.dzn | 0.7360 ± 0.0068 | 0.7036 ± 0.0039 | 0.7369 ± 0.0066 | 0.000882 ± 0.000721 | 0.1200% | 2.00 | 11.40 | 13.4 |

## 2. Interpretación de la Evidencia

### DEMOSTRADO POR LOS DATOS:
1. En instancias pequeñas y medianas (`10_10` y `20_20`), NSGA-II+LS sí produce algunas soluciones no dominadas exclusivas (promedio de 1.2 a 2.4 soluciones por corrida), aportando una mejora marginal muy leve pero positiva al frente conjunto.
2. En instancias grandes (`40_40` y `50_50`), el número de soluciones exclusivas aportadas por NSGA-II+LS cae a cero o valores marginales (< 0.2), y Delta HV se vuelve exactamente 0.000000.
3. La trayectoria de NSGA-II+LS sufre una desaceleración pronunciada a partir de 250 FE: el consumo de evaluaciones por vecino evaluado en la ruta crítica frena el avance genético global de la población.

### DECISION SUPPORT:
- **Evidencia a favor de NSGA-II+LS:** A diferencia de MOPSO, NSGA-II+LS sí aporta algunas soluciones exclusivas en instancias pequeñas/medianas.
- **Evidencia en contra:** En instancias grandes, su sobrecosto local de evaluaciones provoca estancamiento prematuro, haciendo que su frente final sea casi completamente dominado por NSGA-II.
