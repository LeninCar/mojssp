# Informe de Validación Técnica, Dinámica Adaptativa y Métricas de Cierre (F2.6)

Este documento presenta la verificación técnica exhaustiva de los pilares metodológicos de cierre de la Fase 2:
1. Reconstrucción algorítmica exacta de SW-UCB y reproducción de las decisiones.
2. Procedencia y distinción entre frentes standalone y de portafolio en el análisis de complementariedad.
3. Evaluación del coste computacional macroscópico y limitaciones de instrumentación.
4. Consolidación de pruebas estadísticas con corrección formal por comparaciones múltiples.
5. Verificación de las ocho configuraciones y diez instancias base de desarrollo.

---

## 1. Verificación Estructural de Instancias y Configuraciones

El conjunto experimental de desarrollo de la Fase 2 comprende exactamente **ocho configuraciones dimensionales** y **diez instancias base independientes**, distribuidas como sigue:

| Configuración | Dimensiones ($J \times M$) | Operaciones | Instancia Base | Perfil Experimental |
| :---: | :---: | :---: | :--- | :--- |
| **C1_5x5** | $5 \times 5$ | 25 | `base_c01_5x5_b03` | Base balanceado |
| **C1_5x5** | $5 \times 5$ | 25 | `base_c01_5x5_b05_tard_med` | Tardiness media |
| **C2_10x10** | $10 \times 10$ | 100 | `base_c02_10x10_b03_tard_high` | Tardiness alta |
| **C2_10x10** | $10 \times 10$ | 100 | `base_c02_10x10_b04_nrg_strong` | Energía fuerte |
| **C3_20x10** | $20 \times 10$ | 200 | `base_c03_20x10_b04_btnk_high` | Cuello de botella alto |
| **C4_10x20** | $10 \times 20$ | 200 | `base_c04_10x20_b04` | Base balanceado |
| **C5_20x20** | $20 \times 20$ | 400 | `base_c05_20x20_b03_tard_med` | Tardiness media |
| **C6_30x20** | $30 \times 20$ | 600 | `base_c06_30x20_b03_tard_high` | Tardiness alta |
| **C7_40x20** | $40 \times 20$ | 800 | `base_c07_40x20_b03_nrg_strong` | Energía fuerte |
| **C8_50x50** | $50 \times 50$ | 2500 | `base_c08_50x50_b03_btnk_high` | Cuello de botella alto |

Cada una de las 10 instancias base se evaluó bajo **3 semillas maestras** (42, 43, 44) y **5 métodos** (MOEA/D, NSGA-II, SPEA2, Portafolio Uniforme y Portafolio Adaptativo DMAB), produciendo **150 trayectorias continuas**. En cada trayectoria se registraron checkpoints acumulados en los hitos presupuestarios de 1.000, 3.000 y 5.000 FE, generando un total de **450 registros de hitos presupuestarios**.

---

## 2. Reconstrucción Exacta de SW-UCB y Reproducción de Decisiones

Se auditó la implementación de `SlidingWindowUCB` ([`src/mojssp/dmab.py`](file:///c:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-dmab/src/mojssp/dmab.py)) y se contrastó contra los registros del log de bloques ([`budget_portfolio_blocks.csv`](file:///c:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/budget_diagnostic/budget_portfolio_blocks.csv)).

### A. Prueba de reproducción bit a bit
Se simuló la lógica exacta de selección de `SlidingWindowUCB` inicializado con la semilla de cada corrida y alimentado bloque a bloque con las recompensas históricas:
- **Total de bloques verificados en fase de selección adaptativa:** 2.910 decisiones (90 bloques de sondeo inicial + 2.820 bloques adaptativos UCB).
- **Decisiones reproducidas de forma exacta:** **2.910 de 2.910 (100.00% de coincidencias, 0 discrepancias)**.
- **Conclusión:** Se confirmó de manera determinista que la implementación del selector, el cálculo logarítmico, el tamaño de ventana ($W=10$), el manejo de la cola FIFO y la regla de desempate mediante el generador pseudoaleatorio reproducen exactamente cada decisión ejecutada en los experimentos.

### B. Dinámica de los términos del índice UCB
$$I_{i,t} = \bar{\mu}_{i,W} + c \sqrt{\frac{\ln(\min(t, W))}{N_{i,W}}}$$

| Métrica del Selector | Valor Observado | Interpretación Metodológica |
| :--- | :---: | :--- |
| **Término de Explotación medio ($\bar{\mu}_{i,W}$)** | $0.00169$ | Magnitud promedio de las mejoras $\Delta HV$ en la ventana |
| **Término de Exploración medio ($c \sqrt{\ln(t)/N_{i,W}}$)** | $0.05978$ | Magnitud del bonus de incertidumbre con $c = 0.07$ |
| **Ratio Exploración / Explotación medio** | **35.4 veces** | La incertidumbre estadística predomina sobre el término empírico |
| **Coincidencia Explotación == Exploración** | $25.21\%$ (711 bloques) | En 1 de cada 4 bloques ambos términos eligen el mismo brazo |
| **Inversión por Exploración** | $64.11\%$ (1.808 bloques) | En casi 2 de cada 3 bloques el bonus de exploración modifica la elección |
| **Frecuencia de recompensa nula ($\Delta HV = 0$)** | $21.95\%$ global | $10.95\%$ en bloques 6–20; $22.08\%$ en bloques 21–60; $25.17\%$ en bloques 61–100 |

---

## 3. Procedencia de Frentes y Análisis de Complementariedad

### A. Procedencia y distinción de conjuntos
Los frentes de Pareto utilizados en el análisis de complementariedad provienen del archivo [`budget_fronts.jsonl`](file:///c:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/budget_diagnostic/budget_fronts.jsonl), que contiene 450 frentes registrados al finalizar cada hito presupuestario (90 frentes por método):
1. **Frentes Standalone:** Frentes generados por ejecuciones continuas de MOEA/D, NSGA-II y SPEA2 evaluados de forma aislada.
2. **Frentes de Portafolio:** Frentes consolidados en el Archivo Global Pareto de los portafolios Uniforme y Adaptativo.

### B. Unión no dominada de corridas standalone independientes (a 5.000 FE)
La unión de las soluciones no dominadas de las tres corridas continuas (que acumulan un esfuerzo combinado de $3 \times 5.000 = 15.000$ FE) presenta las siguientes características:
- **Tamaño medio del frente conjunto no dominado:** $88.63$ soluciones.
- **Aportes exclusivos de MOEA/D:** $41.90$ soluciones ($47.3\%$).
- **Aportes exclusivos de NSGA-II:** $18.23$ soluciones ($20.6\%$).
- **Aportes exclusivos de SPEA2:** $28.50$ soluciones ($32.2\%$).
- **Soluciones compartidas idénticas:** $0.00$ soluciones ($0.0\%$).
- **Aporte marginal de Hypervolume al retirar MOEA/D:** $+0.088316$.
- **Aporte marginal de Hypervolume al retirar NSGA-II:** $+0.005342$.
- **Aporte marginal de Hypervolume al retirar SPEA2:** $+0.010232$.
- **Suma de aportes marginales:** $0.103890$ frente a un Hypervolume total conjunto de $1.047266$.

### C. Aclaración metodológica
Las contribuciones marginales no son aditivas debido al solapamiento del hipervolumen dominado compartido. Asimismo, los frentes del portafolio (que operan bajo una cota estricta de 5.000 FE compartidas) no deben compararse directamente contra la unión de 15.000 FE acumuladas de tres ejecuciones independientes sin considerar la asimetría en el esfuerzo computacional.

---

## 4. Coste Computacional y Tiempos de Ejecución

- **Limitación de instrumentación:** Se verificó que el repositorio no cuenta con instrumentación de profiling fino dentro del ciclo de orquestación (no se mide por separado el tiempo de `select_arm`, `dmab.update` ni `compute_reward`).
- **Medición macroscópica:** Se evaluó el tiempo de pared total acumulado de las trayectorias en [`budget_runs.csv`](file:///c:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/budget_diagnostic/budget_runs.csv):
  - Portafolio Uniforme (Round-Robin): $816.61$ segundos acumulados across all runs.
  - Portafolio Adaptativo (DMAB): $814.87$ segundos acumulados across all runs.
  - **Diferencia relativa:** $-0.21\%$ (indistinguible a nivel macroscópico).
- **Conclusión:** El tiempo de pared de DMAB es equivalente al de la asignación uniforme, lo que demuestra que la toma de decisiones no impone una penalización que afecte la viabilidad técnica.

---

## 5. Inferencia Estadística y Corrección por Comparaciones Múltiples

Se presentan los resultados agregados sobre las **$N = 10$ bases independientes** ($df = 9$):

### A. Familia Principal: DMAB vs. Uniforme (Holm-Bonferroni, $\alpha = 0.05$, $m = 3$)
- **Hito 3.000 FE:** $\bar{D} = +0.0054$, IC 95% $[+0.0021, +0.0087]$, $p = 0.001953$ (umbral Holm: $0.016667$). **Rechazo de $H_0$ (diferencia estadísticamente significativa detectada, tamaño de efecto $d = +1.17$).**
- **Hito 5.000 FE:** $\bar{D} = +0.0033$, IC 95% $[+0.0008, +0.0057]$, $p = 0.009766$ (umbral Holm: $0.025000$). **Rechazo de $H_0$ (diferencia estadísticamente significativa detectada, tamaño de efecto $d = +0.94$).**
- **Hito 1.000 FE:** $\bar{D} = -0.0007$, IC 95% $[-0.0041, +0.0027]$, $p = 0.769531$ (umbral Holm: $0.050000$). **No se rechaza $H_0$ (sin diferencia estadísticamente significativa detectada).**

*Nota metodológica:* No se califica 3.000 FE como "presupuesto óptimo"; simplemente representa el hito evaluado donde la diferencia observada fue mayor dentro de los tres puntos discretos analizados.

### B. Familia Exploratoria: Portafolios vs. Algoritmos Individuales (FDR Benjamini-Hochberg, $q = 0.05$, $m = 18$)
En las 18 comparaciones pareadas contra MOEA/D, NSGA-II y SPEA2 en los tres hitos de presupuesto, todos los contrastes resultaron estadísticamente significativos a favor de los algoritmos continuos individuales ($p \le 0.0137 < \text{umbral BH}$).
