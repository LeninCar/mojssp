# Informe Formal de Auditoría Científica F2.5.2
**Auditoría Estadística, Metodológica y Técnica para el Cierre de Fase 2**  
*Tesis:* Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo  
*Brazos auditados:* `MOEA/D`, `NSGA-II`, `SPEA2`  
*Políticas auditadas:* `Uniforme (Round-Robin)` y `Adaptativa (SW-UCB)`  
*Fecha de dictamen:* 2026-10-14  

---

## 1. Alcance de la Auditoría

Se realizó una auditoría rigurosa e independiente sobre los 600 registros experimentales generados en la Fase 2:
- 150 corridas del piloto de 1.000 FE (`results/expanded_portfolio_phase2/pilot/`).
- 450 registros de control del diagnóstico de presupuesto a 1.000, 3.000 y 5.000 FE (`results/expanded_portfolio_phase2/budget_diagnostic/`).

Se verificaron las 10 bases de desarrollo independientes, las 3 semillas maestras ($s \in \{42, 43, 44\}$), los cinco métodos de optimización, la totalidad de los $15\,000$ checkpoints de hypervolume y los $6\,000$ bloques de ejecución.

---

## 2. Resumen de Integridad Experimental (10/10 PASS)

| Verificación Auditada | Criterio de Aceptación | Estado Observado | Dictamen |
| :--- | :--- | :--- | :---: |
| **CHK_01: Conteo de Registros** | Exactamente 450 registros en budget_runs.csv | 450 registros | **PASS** |
| **CHK_02: Hitos de Presupuesto** | Exactamente [1000, 3000, 5000] FE | [1000, 3000, 5000] FE | **PASS** |
| **CHK_03: Unicidad de Corridas** | 450 run_ids únicos sin duplicados | 450 run_ids únicos | **PASS** |
| **CHK_04: Cero Overshoot** | `evaluations_used == budget`, overshoot == 0 | Mínimo 0, Máximo 0 | **PASS** |
| **CHK_05: Cero Excepciones** | Estado SUCCESS, error == '' | 0 errores registrados | **PASS** |
| **CHK_06: Conteo de Checkpoints** | 15.000 checkpoints (100 por corrida) | 15.000 checkpoints | **PASS** |
| **CHK_07: Monotonicidad de HV** | HV no decreciente en archivos acumulativos | 0 transiciones negativas | **PASS** |
| **CHK_08: Coherencia F2.4 vs F2.5.1** | Identidad binaria a 1.000 FE | Max dif HV = 0.0, Arch dif = 0 | **PASS** |
| **CHK_09: Suma de Asignaciones** | Suma de asignaciones coincide con hito | 0 discrepancias | **PASS** |
| **CHK_10: Conteo de Bloques** | Exactamente 100 bloques por corrida de portafolio | 100 bloques en todas | **PASS** |

Detalle completo en [`integrity_checks.csv`](file:///c:/Users/lenin/Documents/Ingenier%C3%ADa/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/closure_audit/integrity_checks.csv).

---

## 3. Auditoría de Comparabilidad y Revisión de `max_generations=None`

Se auditó formalmente el ajuste introducido en `src/mojssp/runner.py` durante F2.5.1:
1. **Comportamiento previo:** En `NSGA2Arm.__init__`, el parámetro `max_generations` tenía por defecto el valor `50`. A $N=30$, el algoritmo alcanzaba $30 + 50 	imes 30 = 1\,530$ evaluaciones y activaba `self._completed = True`.
2. **Impacto en 1.000 FE:** **Nulo.** Para $1\,000$ FE, el algoritmo solo requiere $pprox 32.3$ generaciones, por lo que nunca alcanzó el límite de 50. La verificación empírica demostró identidad binaria absoluta (`0.000000000000`) entre ambas versiones a 1.000 FE.
3. **Impacto en 3.000 y 5.000 FE:** **Correctivo y necesario.** Sin `max_generations=None`, NSGA-II se habría detenido prematuramente a 1.530 FE, invalidando la comparación presupuestaria frente a MOEA/D y SPEA2.
4. **Calificación metodológica:** Se clasifica formalmente como un **bugfix defensivo de integración del runner**, indispensable para cumplir el principio de paridad presupuestaria en evaluaciones (FE).

---

## 4. Auditoría Estadística Agregada por Base (N = 10)

Respetando el diseño jerárquico donde las 10 bases son las unidades independientes y las 3 semillas son réplicas intra-base, se consolidaron las diferencias medias pareadas:

### Presupuesto: 1.000 FE
| Contraste | Dif. Media ($ar{D}$) | IC 95% ($ar{D}$) | Mediana | Victorias/Empates/Derrotas (Base) | Victorias/Empates/Derrotas (Corrida) | $d$ de Cohen | $p$-valor (Wilcoxon) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **DMAB − Uniform** | -0.000699 | [-0.004063, +0.002665] | +0.000045 | 7 / 0 / 3 | 12 / 11 / 7 | -0.15 | 0.7695 (n.s.) |
| **DMAB − MOEA/D** | -0.034219 | [-0.047041, -0.021398] | -0.033675 | 0 / 0 / 10 | 1 / 0 / 29 | -1.91 | **0.0020** |
| **DMAB − NSGA-II** | -0.027043 | [-0.036056, -0.018029] | -0.024985 | 0 / 0 / 10 | 2 / 0 / 28 | -2.15 | **0.0020** |
| **DMAB − SPEA2** | -0.023991 | [-0.031958, -0.016025] | -0.023871 | 0 / 0 / 10 | 0 / 0 / 30 | -2.15 | **0.0020** |

### Presupuesto: 3.000 FE
| Contraste | Dif. Media ($ar{D}$) | IC 95% ($ar{D}$) | Mediana | Victorias/Empates/Derrotas (Base) | Victorias/Empates/Derrotas (Corrida) | $d$ de Cohen | $p$-valor (Wilcoxon) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **DMAB − Uniform** | **+0.005427** | **[+0.002122, +0.008732]** | **+0.004775** | **10 / 0 / 0** | **25 / 1 / 4** | **+1.17** | **0.0020** |
| **DMAB − MOEA/D** | -0.047178 | [-0.058510, -0.035846] | -0.046973 | 0 / 0 / 10 | 0 / 0 / 30 | -2.98 | **0.0020** |
| **DMAB − NSGA-II** | -0.030006 | [-0.040333, -0.019679] | -0.026487 | 0 / 0 / 10 | 2 / 0 / 28 | -2.08 | **0.0020** |
| **DMAB − SPEA2** | -0.022883 | [-0.032931, -0.012835] | -0.023636 | 0 / 0 / 10 | 5 / 0 / 25 | -1.63 | **0.0020** |

### Presupuesto: 5.000 FE
| Contraste | Dif. Media ($ar{D}$) | IC 95% ($ar{D}$) | Mediana | Victorias/Empates/Derrotas (Base) | Victorias/Empates/Derrotas (Corrida) | $d$ de Cohen | $p$-valor (Wilcoxon) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **DMAB − Uniform** | **+0.003251** | **[+0.000789, +0.005712]** | **+0.002582** | **9 / 0 / 1** | **23 / 1 / 6** | **+0.94** | **0.0098** |
| **DMAB − MOEA/D** | -0.054232 | [-0.069975, -0.038489] | -0.053029 | 0 / 0 / 10 | 0 / 0 / 30 | -2.46 | **0.0020** |
| **DMAB − NSGA-II** | -0.030240 | [-0.041994, -0.018486] | -0.037757 | 0 / 0 / 10 | 2 / 0 / 28 | -1.84 | **0.0020** |
| **DMAB − SPEA2** | -0.019567 | [-0.031683, -0.007452] | -0.023591 | 1 / 0 / 9 | 7 / 0 / 23 | -1.16 | **0.0137** |

Detalle completo en [`paired_differences_by_base.csv`](file:///c:/Users/lenin/Documents/Ingenier%C3%ADa/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/closure_audit/paired_differences_by_base.csv) y [`statistical_summary.csv`](file:///c:/Users/lenin/Documents/Ingenier%C3%ADa/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/closure_audit/statistical_summary.csv).

---

## 5. Auditoría del Mecanismo Adaptativo SW-UCB

Se reconstruyó la totalidad de los $2\,820$ índices UCB en las decisiones adaptativas:
- **Término de Explotación ($ar{X}_{i, W}$):** Media $= 0.001689$, Mediana $= 0.000429$, Máximo $= 0.046850$.
- **Término de Exploración ($c \sqrt{\ln(\min(t_a, W))/N_{i, W}}$):** Media $= 0.059775$, Mediana $= 0.061326$.
- **Ratio Exploración / Explotación:** **$35.40 	imes$**
- **Interpretación física:** Debido a que las recompensas marginales $\Delta HV$ son del orden de $10^{-3}$, el factor $c = 0.07$ domina la decisión en más del $95\%$ de los bloques. Esto explica por qué el portafolio asigna entre $31.5\%$ y $35.5\%$ a cada brazo y no converge a un único algoritmo.

Detalle en [`adaptation_audit.csv`](file:///c:/Users/lenin/Documents/Ingenier%C3%ADa/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/closure_audit/adaptation_audit.csv).

---

## 6. Auditoría de Complementariedad y Frente Conjunto

Se auditó la unión no dominada de frentes individuales y la contribución de los brazos:
- Las soluciones compartidas representan el $0\%$ en la mayoría de las instancias continuas debido a la naturaleza densa y continua de los objetivos decodificados (makespan, tardiness, energía), lo que ratifica que cada algoritmo explora nichos geométricos diferenciados.
- **Contribución marginal no aditiva:** Se confirmó que la suma de aportes marginales al Hypervolume por eliminación de brazos ($\sum \Delta HV_{	ext{marginal}}$) no coincide con el HV total de la unión, reflejando el solapamiento parcial de los volúmenes dominados.
- **Diferencia conceptual clave:** La complementariedad observada en Fase 1 corresponde a frentes generados con $1\,000$ FE dedicadas por algoritmo ($3\,000$ FE totales acumuladas). En un portafolio con presupuesto compartido de $1\,000$ FE, cada algoritmo recibe solo $pprox 333$ FE, lo que impide alcanzar la misma riqueza de frentes.

Detalle en [`complementarity_audit.csv`](file:///c:/Users/lenin/Documents/Ingenier%C3%ADa/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/closure_audit/complementarity_audit.csv).

---

## 7. Dictamen Final de Cierre

# **APTO CON OBSERVACIONES**

La arquitectura de software, la reproducibilidad y la contabilidad experimental de la Fase 2 están **100% verificadas y aprobadas**. No se requiere reejecutar ningún algoritmo.  
El cierre formal se aprueba bajo la condición metodológica de incorporar las correcciones en el reporte de tesis estipuladas en [`closure_readiness.md`](file:///c:/Users/lenin/Documents/Ingenier%C3%ADa/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/closure_audit/closure_readiness.md), asumiendo honestamente las limitaciones de la arquitectura pasiva sin inyección y proponiendo la inyección de soluciones y la recompensa multiescala como los pilares de la Fase 3.
