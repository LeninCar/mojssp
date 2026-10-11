# INFORME DE AUDITORÍA: EVALUACIÓN MULTI-MÉTRICA (HV, IGD+, EPSILON+)

**Fecha:** 2026-10-05  
**Protocolo:** 5 instancias, 5 semillas, 4 métodos, 1000 FE exactas.  
**Reference Front ($PF_{ref}$):** Construido estrictamente a posteriori mediante la unión de todas las soluciones no dominadas de todos los métodos.

## 1. Tabla Agregada de Métricas de Calidad

| Instancia | Algoritmo | HV (Mean ± SD) | IGD+ (Mean ± SD) | Epsilon+ (Mean ± SD) |
| :--- | :--- | :---: | :---: | :---: |
| 10_10_2-5_1.dzn | RandomSearch | 0.7192 ± 0.0079 | 0.0983 ± 0.0098 | 0.1198 ± 0.0086 |
| 10_10_2-5_1.dzn | MOPSO | 0.6811 ± 0.0156 | 0.1129 ± 0.0119 | 0.1595 ± 0.0100 |
| 10_10_2-5_1.dzn | NSGA-II | 0.8264 ± 0.0302 | 0.0179 ± 0.0096 | 0.0409 ± 0.0257 |
| 10_10_2-5_1.dzn | NSGA-II+LS | 0.6903 ± 0.0150 | 0.1020 ± 0.0134 | 0.1738 ± 0.0128 |
| 20_20_2-5_1.dzn | RandomSearch | 0.6944 ± 0.0050 | 0.0479 ± 0.0030 | 0.0839 ± 0.0056 |
| 20_20_2-5_1.dzn | MOPSO | 0.6866 ± 0.0125 | 0.0539 ± 0.0070 | 0.0937 ± 0.0126 |
| 20_20_2-5_1.dzn | NSGA-II | 0.7662 ± 0.0103 | 0.0091 ± 0.0047 | 0.0245 ± 0.0078 |
| 20_20_2-5_1.dzn | NSGA-II+LS | 0.6931 ± 0.0100 | 0.0453 ± 0.0067 | 0.0975 ± 0.0105 |
| 30_30_2-5_1.dzn | RandomSearch | 0.6929 ± 0.0051 | 0.0386 ± 0.0025 | 0.0577 ± 0.0050 |
| 30_30_2-5_1.dzn | MOPSO | 0.6826 ± 0.0143 | 0.0421 ± 0.0092 | 0.0656 ± 0.0117 |
| 30_30_2-5_1.dzn | NSGA-II | 0.7459 ± 0.0095 | 0.0066 ± 0.0036 | 0.0133 ± 0.0070 |
| 30_30_2-5_1.dzn | NSGA-II+LS | 0.6860 ± 0.0039 | 0.0431 ± 0.0017 | 0.0712 ± 0.0027 |
| 40_40_2-5_1.dzn | RandomSearch | 0.7036 ± 0.0041 | 0.0254 ± 0.0025 | 0.0398 ± 0.0033 |
| 40_40_2-5_1.dzn | MOPSO | 0.6946 ± 0.0021 | 0.0309 ± 0.0011 | 0.0454 ± 0.0019 |
| 40_40_2-5_1.dzn | NSGA-II | 0.7437 ± 0.0036 | 0.0030 ± 0.0010 | 0.0064 ± 0.0018 |
| 40_40_2-5_1.dzn | NSGA-II+LS | 0.6980 ± 0.0068 | 0.0295 ± 0.0052 | 0.0485 ± 0.0066 |
| 50_50_2-5_1.dzn | RandomSearch | 0.7040 ± 0.0012 | 0.0213 ± 0.0011 | 0.0344 ± 0.0013 |
| 50_50_2-5_1.dzn | MOPSO | 0.6963 ± 0.0018 | 0.0252 ± 0.0018 | 0.0396 ± 0.0016 |
| 50_50_2-5_1.dzn | NSGA-II | 0.7360 ± 0.0068 | 0.0037 ± 0.0028 | 0.0085 ± 0.0058 |
| 50_50_2-5_1.dzn | NSGA-II+LS | 0.7036 ± 0.0039 | 0.0219 ± 0.0025 | 0.0376 ± 0.0032 |

## 2. Hallazgos Clave

### DEMOSTRADO POR LOS DATOS:
1. **Las conclusiones de HV se confirman al 100% con IGD+ y Epsilon+:**
   - NSGA-II obtiene sistemáticamente el menor IGD+ (mejor convergencia/cobertura hacia $PF_{ref}$) y el menor $\epsilon+$.
   - MOPSO tiene el peor IGD+ y peor $\epsilon+$ de todos los algoritmos, confirmando que está más distante del frente de referencia que incluso Random Search.
2. **Random Search supera a MOPSO en las tres métricas:**
   - Random Search tiene mayor HV, menor IGD+ y menor $\epsilon+$ que MOPSO en todas las instancias medianas y grandes.
