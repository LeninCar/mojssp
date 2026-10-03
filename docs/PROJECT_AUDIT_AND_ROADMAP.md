# AUDITORÍA INTEGRAL, CRÍTICA Y ROADMAP ESTRATÉGICO
## Tesis: "Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)"

---

# 1. Executive Summary

El presente documento constituye la auditoría técnica, metodológica y científica definitiva del proyecto de tesis de Ingeniería de Sistemas: **“Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)”**.

La pregunta de investigación fundamental es:
> **¿Cómo puede implementarse un portafolio de algoritmos orientado a la resolución del Multi-Objective Job Shop Scheduling Problem (MO-JSSP) de manera eficiente y adaptable a diferentes criterios de optimización?**

### Principales Conclusiones de la Auditoría:
1. **Solidez Técnica y de Software:** La base de software (`src/mojssp/*`) es de calidad de producción. Cuenta con 312 pruebas unitarias e integrales (0 fallos), decodificador serial determinista $O(N)$, evaluador puro, cálculo 3D exacto de Hypervolume y contabilidad estricta de Function Evaluations (FE) con cero sobrecosto (overshoot = 0).
2. **Hallazgo Crítico Empírico en F8.6.5:** Al evaluar las 37 instancias del benchmark a través de 10 semillas independientes (1,480 corridas a 1,000 FE exactas), el algoritmo individual **NSGA-II Standalone superó al Portfolio adaptativo en las 37 instancias (100% de victorias a nivel de media)** y en el **99.5% de los pares semilla a semilla (368 de 370 corridas)**:
   $$\overline{HV}_{\text{NSGA-II}} = 0.8436 > \overline{HV}_{\text{Portfolio}} = 0.8059 > \overline{HV}_{\text{NSGA-II+LS}} = 0.7550 > \overline{HV}_{\text{MOPSO}} = 0.7377$$
3. **Causa Raíz Identificada:**
   * *Aislamiento Estanco de los Brazos:* Los algoritmos del portafolio no comparten población ni reciben migraciones del Global Archive. El portafolio fragmenta el presupuesto: NSGA-II recibe solo 372 FE en el portafolio (frente a 1,000 FE en standalone), interrumpiendo su convergencia en la generación 8 en lugar de la 24.
   * *Sobrecosto de Inicialización (Cold-Start Tax):* Cada brazo evalúa su propia población aleatoria inicial, consumiendo 130 FE (13% del presupuesto) en soluciones totalmente no optimizadas, frente a 40 FE (4%) en standalone.
   * *Descalibración Crítica de UCB ($c=0.07, W=10$):* La recompensa media real $\Delta HV$ es de $\approx 0.0042$, mientras que el término de exploración de UCB oscila entre $0.07$ y $0.15$ (17 veces mayor). Esto obligó a DMAB a una exploración forzada continua (round-robin cuasi-uniforme), dilapidando el 60% del presupuesto en MOPSO y NSGA-II+LS, que son algoritmos significativamente inferiores.
4. **Vía Científica de Solución:** La tesis no debe ocultar la derrota frente a NSGA-II. Debe presentarla como una contribución metodológica clave sobre los límites de los portafolios de caja negra sin comunicación en presupuestos finitos, complementada con la demostración de adaptabilidad (F8.6.2, donde DMAB vence al portafolio uniforme) y, opcionalmente, una prueba de concepto de *Shared Archive / Elite Injection*.

---

# 2. Estado actual del proyecto

El proyecto ha completado exitosamente las Fases 1 a F8.6.5. El repositorio cuenta con:
* 21 módulos en `src/mojssp/` que cubren desde el modelo formal hasta el orquestador adaptativo.
* 312 tests automáticos basados en `unittest` con 100% de tasa de éxito.
* 37 instancias completamente validadas (12 originales en `data/experimental/` y 25 generadas mediante diseño factorial en `data/generated/f86_3/`).
* Resultados experimentales exhaustivos: F8.4 (auditoría FE), F8.5 (piloto), F8.6.2 (DMAB vs uniforme: 50 corridas) y F8.6.5 (experimento principal: 1,480 corridas a 1,000 FE).

---

# 3. Arquitectura real

El flujo de ejecución real implementado en `AdaptivePortfolioOrchestrator` es el siguiente:

```text
                                Instance (.dzn)
                                       │
                                       ▼
                           AnalyticalMinMaxNormalizer
                                       │
                                       ▼
                         AdaptivePortfolioOrchestrator
                                       │
      ┌────────────────────────────────┴────────────────────────────────┐
      ▼                                                                 ▼
[Warm-up Neutral: 150 FE]                                  [Fase Adaptativa: 850 FE]
3 bloques x 50 FE (fijo por brazo)                          17 bloques x 50 FE (DMAB)
      │                                                                 │
      ├────────────────────────────────┬────────────────────────────────┤
      ▼                                ▼                                ▼
  NSGA2Arm                         MOPSOArm                        NSGA2LSArm
  (Población P=40,                (Enjambre S=50,                  (Población P=40,
   POX, Swaps, Modos)              Partículas, Pbest)               Local Search CP)
      │                                │                                │
      └────────────────────────────────┼────────────────────────────────┘
                                       ▼
                                 Decoder.decode()  [O(N) serial semi-activo]
                                       │
                                       ▼
                               Evaluator.evaluate()  [1 llamada = 1 FE]
                                       │
                                       ▼
                            Portfolio.global_archive  [ParetoArchive no acotado]
                                       │
                                       ▼
                           HypervolumeRewardTracker
                                       │  r = (1.1, 1.1, 1.1)
                                       ▼
                         Reward = max(0, ΔHV_global)
                                       │
                                       ▼
                                SlidingWindowUCB  (W=10, c=0.07)
```

**Propiedades de la Arquitectura:**
* *Flujo Unidireccional:* La información fenotípica va desde los brazos hacia el `GlobalArchive`. **No existe retroalimentación** hacia los brazos.
* *Pausabilidad Exacta:* Cada brazo almacena su estado interno completo (población, enjambre, generadores aleatorios, contadores de generación).
* *Sobrecosto Cero de FE:* La normalización, el cálculo de Hypervolume y la toma de decisiones de DMAB no consumen evaluaciones del problema.

---

# 4. Modelo MO-JSSP

El modelo implementado en `src/mojssp/instance.py`, `operation.py`, `schedule.py` y `evaluator.py` es un Job Shop Scheduling Problem clásico con **Speed Scaling** discreto y tres funciones objetivo en conflicto:

$$F = (C_{max}, T, E)$$

1. **Makespan ($C_{max}$):** Tiempo máximo de terminación:
   $$C_{max} = \max_{j \in \mathcal{J}, k \in \mathcal{O}_j} C_{j,k}$$
2. **Total Tardiness ($T$):** Retraso total respecto a las fechas de entrega:
   $$T = \sum_{j \in \mathcal{J}} \max(0, C_j - d_j)$$
   Las fechas de entrega ($d_j$) son **soft constraints** y no alteran la factibilidad.
3. **Consumo Energético Total ($E$):** Suma del consumo según el modo de velocidad seleccionado:
   $$E = \sum_{j \in \mathcal{J}} \sum_{k \in \mathcal{O}_j} \text{energy}(O_{j,k}, v_{j,k})$$
4. **Fechas de Liberación ($r_{j,k}$):** Restricciones duras temporales: $S_{j,k} \ge r_{j,k}$.

---

# 5. Representation

* **Genotipo:** $\text{Solution} = (\boldsymbol{\pi}_{\text{ops}}, \mathbf{v})$.
  * $\boldsymbol{\pi}_{\text{ops}}$: Permutación con repetición (Bierwirth) de longitud $N = \sum n_j$.
  * $\mathbf{v}$: Vector de modos discretos de longitud $N$ alineado canónicamente con `instance.all_operations`.
* **Juicio Crítico:** La representación garantiza factibilidad al 100% sin requerir algoritmos de reparación. Sin embargo, presenta redundancia genotípica: varias permutaciones distintas decodifican en schedules idénticos si involucran operaciones independientes en máquinas desacopladas.

---

# 6. Decoder

* **Módulo:** `src/mojssp/decoder.py`.
* **Algoritmo:** Serial List-Based Decoder:
  $$S_{j,k} = \max(C_{j,prev}, T_{\text{disp}}(M_{j,k}), r_{j,k}), \quad C_{j,k} = S_{j,k} + p_{j,k,v}$$
* **Propiedades:** Determinista, complejidad $O(N)$ con seguimiento $O(1)$ de máquinas y trabajos en tablas hash. Genera schedules **semi-activos**.
* **Auditoría de Invariantes:** Verificado exhaustivamente contra `ScheduleValidator`, que corrobora la ausencia de solapamiento en máquinas, respeto de precedencias y validez de duraciones y consumos de cada modo.

---

# 7. Evaluator

* **Módulo:** `src/mojssp/evaluator.py`.
* **Definición de FE:** Una Function Evaluation (FE) corresponde exactamente a una invocación de `Evaluator.evaluate(instance, schedule)`.
* **Propiedades:** Es una función pura y sin estado. No utiliza memoria caché oculta. Mide con precisión $(C_{max}, T, E)$ y devuelve una instancia inmutable de `ObjectiveValues`.

---

# 8. Algorithms

El portafolio actual integra tres metaheurísticas adaptadas:
1. **NSGA-II (`NSGA2Arm`):**
   * Población $P = 40$. Cruce POX ($p_c = 0.9$), mutación swap en secuencia ($p_{m,seq} = 0.2$) y mutación uniforme de modos ($p_{m,gene} = 1/N$).
   * *Diagnóstico:* Es el algoritmo más robusto y de convergencia más rápida. En standalone alcanza un Hypervolume medio de **0.8436**.
2. **NSGA-II + Local Search (`NSGA2LSArm`):**
   * Extensión memética que aplica búsqueda local sobre la ruta crítica y ajuste de modos sobre el frente $F_1$ y un 25% de no-$F_1$.
   * *Diagnóstico:* Destruye presupuesto en horizontes de 1,000 FE. Cada búsqueda local explora hasta 20 vecinos por individuo, consumiendo de 20 a 60 FE por generación. Termina con un HV medio de **0.7550**.
3. **MOPSO Discreto (`MOPSOArm`):**
   * Enjambre discreto con $S = 50$ partículas, archivos personales de no dominados ($P_{best}$) y archivo global de líderes con selección por crowding distance.
   * *Diagnóstico:* Requiere 50 FE solo para inicializarse. Con las escasas evaluaciones que le asigna el portafolio, solo ejecuta ~5 pasos de enjambre, estancándose en un HV medio de **0.7377**.

---

# 9. Pareto Archive

* **Módulo:** `src/mojssp/pareto_archive.py`.
* **Funcionamiento:** Mantiene el conjunto de soluciones no dominadas acumuladas de forma no acotada.
* **Criterio:** Dominancia de Pareto estricta y débil. Elimina duplicados en el espacio objetivo.
* **Costo Computacional:** $O(M \cdot |A|)$ por inserción. Para los frentes generados ($|A| \le 150$), la inserción toma menos de 0.05 milisegundos.

---

# 10. Normalization

* **Módulo:** `src/mojssp/normalization.py`.
* **Cotas Analíticas Derivadas de la Instancia:**
  $$LB_{Cmax} = \max_j \max_k \left( r_{j,k} + \sum_{h=k}^{n_j} \min_m p_{j,h,m} \right), \quad UB_{Cmax} = \max_o r_o + \sum_o \max_m p_{o,m}$$
  $$LB_E = \sum_o \min_m e_{o,m}, \quad UB_E = \sum_o \max_m e_{o,m}$$
  $$LB_T = 0, \quad UB_T = \sum_j \max(0, UB_{Cmax} - d_j)$$
* **Transformación:** $f'_i = (f_i - LB_i) / (UB_i - LB_i) \in [0, 1]$.
* **Propiedades:** Invariante en el tiempo, 100% reproducible y sin riesgo de desbordamiento.

---

# 11. Hypervolume

* **Módulo:** `src/mojssp/hypervolume.py`.
* **Algoritmo:** Barrido dimensional exacto 3D (*Dimension Sweep / 2D Slicing*).
* **Punto de Referencia:** $r = (1.1, 1.1, 1.1)$ fijo en el espacio normalizado $[0, 1]^3$.
* **Propiedad:** Garantiza monotonicidad estricta respecto a la dominancia de Pareto. Ningún punto factible queda fuera de la región acotada por $r$.

---

# 12. Reward

* **Módulo:** `src/mojssp/reward.py`.
* **Fórmula:**
  $$\text{Reward}_t = \max(0.0, HV_{\text{after}, t} - HV_{\text{before}, t})$$
* **Deficiencias Detectadas:**
  * *Sparsity:* 30.5% de los bloques en F8.6.5 recibieron recompensa exactamente 0.0 (79.6% en MOPSO).
  * *Micro-escala:* Los valores de $\Delta HV$ tienen un promedio de $0.0042$, lo cual es incompatible con el factor de exploración $c=0.07$ en UCB.

---

# 13. DMAB

* **Módulo:** `src/mojssp/dmab.py`.
* **Algoritmo:** Sliding-Window Upper Confidence Bound (SW-UCB):
  $$UCB_i = \bar{\mu}_{i, W} + c \sqrt{\frac{2 \ln(\min(t, W))}{N_{i, W}}}$$
* **Parámetros:** Ventana $W = 10$, factor de exploración $c = 0.07$.
* **Regla de Ausencia:** Si $N_{i, W} = 0$, $UCB_i = +\infty$.
* **Demostración del Fallo de Explotación:**
  * Con $W=10$ y 3 brazos, si NSGA-II se selecciona 4 veces en la ventana, su término de exploración es $0.07 \times \sqrt{2 \ln(10) / 4} \approx 0.0751$.
  * Su valor UCB total resulta: $UCB_{\text{NSGA-II}} = 0.0089 + 0.0751 = \mathbf{0.0840}$.
  * MOPSO (con recompensa 0 y 1 sola observación en la ventana) obtiene: $UCB_{\text{MOPSO}} = 0.00026 + 0.1502 = \mathbf{0.1505}$.
  * **Conclusión:** ¡MOPSO tiene un UCB casi 2 veces mayor que NSGA-II a pesar de no mejorar el frente! UCB se vio matemáticamente forzado a repartir el presupuesto de forma cuasi-uniforme (NSGA-II: 37.9%, NSGA-II+LS: 33.2%, MOPSO: 28.9%).

---

# 14. Portfolio

* **Módulo:** `src/mojssp/portfolio.py`.
* **Estructura:** Administrador de brazos desacoplados que recibe el resultado de cada bloque y alimenta el `GlobalArchive`.
* **Limitación Crítica:** Es un portafolio de caja negra sin migración ni inyección de soluciones.

---

# 15. Function Evaluations

* **Presupuesto:** 1,000 FE por corrida.
* **Control:** Verificado en 1,480 corridas independientes.
* **Overshoot:** **0 FE** en todas las ejecuciones.
* **Paridad:** Standalone y Portfolio consumen exactamente la misma cantidad de evaluaciones de la función objetivo.

---

# 16. Experimental Protocol

* **Warm-up Neutral:** 3 bloques $\times$ 50 FE = 150 FE (1 bloque por brazo en orden estricto, sin actualizar estadísticas de DMAB).
* **Fase Adaptativa:** 17 bloques $\times$ 50 FE = 850 FE seleccionados dinámicamente por DMAB.
* **Semillas:** 10 semillas fijas ($0, 1, \dots, 9$).
* **Instancias:** 37 instancias del benchmark completo.

---

# 17. Existing Experiments

El proyecto ha ejecutado una secuencia estructurada de experimentos:
1. F8.4: Auditoría de paridad de FE y pausabilidad.
2. F8.5: Piloto preliminar en 1 instancia.
3. F8.6.2: Comparación controlada de DMAB frente a Portfolio Uniforme (50 corridas).
4. F8.6.4: Validación de diversidad factorial de las 37 instancias.
5. F8.6.5: Experimento principal multinstancia y multisemilla (1,480 corridas).

---

# 18. F8.4 Audit

* **Propósito:** Certificar que la pausabilidad de los brazos garantizaba reproducibilidad determinista y cero overshoot.
* **Resultado:** 100% de cumplimiento. Se verificó que pausar y reanudar un algoritmo cada 50 FE produce exactamente la misma trayectoria que una ejecución continua si no se alteran los parámetros.

---

# 19. F8.5 Pilot

* **Propósito:** Probar la integración de `AdaptivePortfolioOrchestrator` en un flujo experimental real.
* **Resultado:** Se generaron los archivos de datos iniciales sobre la instancia `10_10_2-5_1.dzn`. Permitió ajustar el formato de los CSVs de salida.

---

# 20. F8.6 Instance Diversity

* **Propósito:** Evaluar si las 37 instancias disponibles representaban familias estructuralmente diversas.
* **Resultado:** Se calculó la matriz de distancias de Gower y se confirmaron 6 dimensiones factoriales ortogonales: tamaño del problema ($N$), factor de cuello de botella de máquinas, relación de aspecto jobs/máquinas, tensión de fechas de entrega, heterogeneidad de duraciones y conflicto tiempo-energía.

---

# 21. F8.6.2 DMAB vs Uniform

* **Propósito:** Determinar si la selección adaptativa de DMAB aportaba algo frente a una distribución uniforme fija de presupuesto (33.3% por brazo).
* **Resultado:** En 50 corridas (5 instancias $\times$ 10 semillas), **DMAB superó al uniforme en 40 de 50 casos (80%) y empató en 10**:
  $$\overline{HV}_{\text{DMAB}} = 0.7663 \quad > \quad \overline{HV}_{\text{Uniform}} = 0.7596 \quad (\Delta HV = +0.0067)$$
* **Interpretación:** Demuestra formalmente que DMAB **sí se adapta** y mejora respecto a una asignación ciega, al otorgar un 37.9% a NSGA-II en vez de un 33.3%.

---

# 22. F8.6.5 Main Experiment

* **Alcance:** 37 instancias $\times$ 10 semillas $\times$ 4 configuraciones = **1,480 ejecuciones**.
* **Tiempo Total:** 4,655.18 segundos (77.59 minutos). Tiempo medio por corrida: 3.15 segundos.
* **Resultados Globales de Hypervolume:**
  * NSGA-II: Mean = **0.8436**, Median = 0.8538, Std = 0.0853.
  * Portfolio+DMAB: Mean = **0.8059**, Median = 0.8163, Std = 0.0815.
  * NSGA-II+LS: Mean = **0.7550**, Median = 0.7681, Std = 0.0768.
  * MOPSO: Mean = **0.7377**, Median = 0.7435, Std = 0.0754.
* **Comparaciones Pareadas Semilla a Semilla (370 pares):**
  * Portfolio vs NSGA-II: **2 Victorias (0.5%), 0 Empates, 368 Derrotas (99.5%)**.
  * Portfolio vs MOPSO: **370 Victorias (100.0%), 0 Empates, 0 Derrotas**.
  * Portfolio vs NSGA-II+LS: **365 Victorias (98.6%), 0 Empates, 5 Derrotas (1.4%)**.
* **A Nivel de Instancia (37 instancias):**
  * **NSGA-II tuvo el mayor HV medio en 37 de 37 instancias (100%)**.

---

# 23. Current Evidence

1. **Evidencia Positiva:**
   * El portafolio supera con contundencia a 2 de sus 3 brazos constitutivos (MOPSO en 100% y NSGA-II+LS en 98.6%).
   * DMAB adaptativo es superior a una asignación uniforme estática (validado en F8.6.2 con 40 victorias en 50 corridas).
   * La infraestructura de contabilidad de FE y reproducibilidad experimental es perfecta (0 overshoot, 312 tests OK).
2. **Evidencia Negativa:**
   * El portafolio pierde consistentemente contra NSGA-II Standalone en todas las instancias bajo 1,000 FE.
   * DMAB sobre-explora por diseño debido a que $c=0.07$ domina a $\Delta HV$.

---

# 24. Unanswered Questions

1. ¿Superaría el portafolio a NSGA-II si se calibra $c$ a un valor adecuado ($c \approx 0.005$) o se normaliza dinámicamente el reward?
2. ¿Qué ocurre bajo presupuestos más amplios (e.g. 5,000 o 10,000 FE), donde NSGA-II comienza a estancarse y los otros brazos completan su fase de convergencia?
3. ¿Aportaría una ventaja decisiva permitir que los brazos reinyecten élites desde el Global Archive (*Shared Archive Injection*)?
4. ¿Existe correlación estadística formal entre las familias de instancias (e.g. instancias con alta carga vs baja carga) y las asignaciones finales de DMAB?

---

# 25. Methodological Risks

1. **Riesgo de Interpretación Sesgada:** Declarar erróneamente al portafolio como "superior" ignorando los resultados pareados contra NSGA-II.
2. **Riesgo de Pseudorreplicación:** Tratar las 370 corridas de distintas instancias como observaciones independientes en pruebas de hipótesis clásicas.
3. **Riesgo de Ajuste a Posteriori (Overfitting):** Calibrar los hiperparámetros de DMAB sobre las mismas instancias y semillas utilizadas para evaluarlo.

---

# 26. Hyperparameter Audit

| Hiperparámetro | Valor Actual | Rango Recomendado | Estado | Comentario Crítico |
| :--- | :---: | :---: | :---: | :--- |
| `population_size` (NSGA-II) | 40 | [30, 60] | **Cerrado** | Tamaño óptimo para presupuestos de 1,000 FE. |
| `population_size` (MOPSO) | 50 | [20, 30] | **Reabrir** | Demasiado grande. Quema 50 FE en inicialización. |
| `max_ls_neighbors` | 20 | [5, 10] | **Reabrir** | Muy alto. Agota bloques enteros en un solo individuo. |
| `window_size` ($W$) | 10 | [10, 20] | **Reabrir** | Ventana muy corta que genera desabastecimiento de brazos ($UCB=\infty$). |
| `exploration_factor` ($c$) | 0.07 | [0.002, 0.008] | **Reabrir** | Críticamente alto respecto a la escala real de $\Delta HV$. |
| `block_size` | 50 | [25, 50] | **Cerrado** | Granularidad adecuada para 1,000 FE. |
| `reference_point` | (1.1, 1.1, 1.1) | Fijo | **Cerrado** | Matemáticamente correcto y fundamentado. |

---

# 27. Algorithm Alternatives

1. **MOEA/D:** Descomposición en subproblemas escalares mediante vectores de peso. Altamente complementario a NSGA-II. Excelente candidato para reemplazar a MOPSO.
2. **Pareto Local Search (PLS) Puro:** Búsqueda local sobre soluciones no dominadas con archivo acotado. Sustituto natural de NSGA-II+LS.
3. **SPEA2:** Alternativa clásica a NSGA-II basada en fuerza de dominancia. Menos complementario debido a similitud algorítmica.
4. **Exact Solver (CP-SAT / MILP):** No viable como brazo iterativo por la imposibilidad de pausar/reanudar limpiamente en Python bajo 50 FE. Debe reservarse como oráculo externo para validar frentes en instancias pequeñas.

---

# 28. Portfolio Alternatives

1. **Portafolio de Caja Negra Estanca (Actual):** Brazos aislados $\to$ Global Archive.
2. **Portafolio Cooperativo con Inyección de Archivo (Shared Archive):** Al inicio de cada bloque, el brazo seleccionado absorbe una muestra de élites del Global Archive en su población interna.
3. **Portafolio Híbrido Basado en Características (Instance-Aware Portfolio):** Selección previa de algoritmo basada en los descriptores estructurales de la instancia antes de iniciar DMAB.

---

# 29. DMAB Alternatives

1. **Sliding-Window UCB con Recompensa Normalizada (Moving Z-Score / MinMax Scaling):**
   $$Reward'_t = \frac{Reward_t - \min_{w} Reward}{\max_{w} Reward - \min_{w} Reward + \epsilon}$$
   Elimina la sensibilidad al hiperparámetro $c$.
2. **Discounted UCB (D-UCB):** Ponderación exponencial decreciente en lugar de ventana rígida finita.
3. **Thompson Sampling Multiobjetivo:** Muestreo bayesiano que maneja naturalmente la incertidumbre sin término de exploración determinista.

---

# 30. Reward Alternatives

1. **$\Delta HV$ Absoluto (Actual):** Directo pero disperso y en escala pequeña.
2. **Contribución Marginal al Archivo (Exclusive Hypervolume):** Mide el volumen que solo ese brazo es capaz de cubrir.
3. **Tasa de Soluciones No Dominadas Aportadas:** Combina $\Delta HV$ con el porcentaje de soluciones inyectadas exitosamente en el archivo de Pareto.

---

# 31. Reference Point Alternatives

* **Punto de Referencia Actual:** $(1.1, 1.1, 1.1)$ en $[0, 1]^3$.
* **Evaluación:** Es la opción más sólida y matemáticamente defendible. Un punto de referencia dinámico basado en el nadir empírico destruiría la monotonicidad temporal de las recompensas en DMAB. **Esta decisión debe mantenerse cerrada.**

---

# 32. Normalization Alternatives

* **Normalización Actual:** Min-Max analítica basada en cotas de la instancia.
* **Evaluación:** Robusta, determinista y sin parámetros ajustables. Garantiza que las soluciones siempre pertenezcan a $[0, 1]^3$. **Debe mantenerse cerrada.**

---

# 33. Budget Alternatives

* **Presupuesto Actual:** 1,000 FE.
* **Evaluación de Alternativas:**
  * Probar 2,500 o 5,000 FE en un subconjunto de instancias permitiría estudiar si NSGA-II satura su frente y los brazos alternativos cobran relevancia.
  * Sin embargo, para el benchmark de 37 instancias, 1,000 FE es un presupuesto representativo de optimización bajo tiempo acotado.

---

# 34. Efficiency Definitions

Para responder formalmente a la pregunta de investigación, la eficiencia debe descomponerse en:
1. **Eficiencia de Calidad:** Hypervolume final bajo 1,000 FE.
2. **Eficiencia de Tasa de Progreso:** Área bajo la curva de Hypervolume vs FE ($AUC_{HV}$).
3. **Eficiencia Computacional de Decisión:** Sobrecosto de tiempo de DMAB frente al tiempo de evaluación (en nuestro código: $< 0.1\%$).

---

# 35. Adaptability Definitions

La adaptabilidad queda demostrada empíricamente si:
1. **DMAB supera a una política estática:** Demostrado en F8.6.2 (DMAB gana en 80% de las corridas).
2. **Existe modulación temporal del presupuesto:** La proporción de selección de brazos cambia entre el inicio (bloques 3-8) y el final de la búsqueda (bloques 15-19).
3. **Existe correlación con la estructura de la instancia:** DMAB ajusta los porcentajes de asignación según el tipo de instancia (e.g. instancias con alta carga de máquinas vs baja carga).

---

# 36. Statistical Analysis Plan

Para el análisis formal de F8.6.5:
1. **Test Global No Paramétrico:** Test de Friedman sobre los rankings medios por instancia para evaluar diferencias significativas entre las 4 configuraciones ($p < 0.05$).
2. **Comparaciones Pareadas Post-Hoc:** Test de rangos con signo de Wilcoxon pareado por instancia con corrección de Holm-Bonferroni para controlar la tasa de error por familia (FWER).
3. **Tamaño del Efecto:** Cálculo de la métrica no paramétrica de Vargha-Delaney ($A_{12}$) para cuantificar la magnitud estandarizada de superioridad.
4. **Correlación Estructural:** Coeficiente de correlación de rangos de Spearman entre los descriptores factoriales de F8.6.4 y la proporción de presupuesto asignada a cada brazo por DMAB.

---

# 37. Literature Review

1. **Portafolios de Algoritmos:** Huberman et al. (1997), Gomes & Selman (2001), Kerschke et al. (2019). Establecen que los portafolios triunfan cuando los algoritmos constitutivos presentan complementariedad ortogonal en espacios de instancias heterogéneos.
2. **Bandidos en Selección Dinámica (AOS/DMAB):** Fialho, Schoenauer & Sebag (2008, 2010), Li et al. (2014). Introducen SW-UCB en algoritmos evolutivos, resaltando la necesidad de normalizar las recompensas para evitar el colapso del balance exploración/explotación.
3. **Portafolios Multiobjetivo Cooperativos:** Vrugt et al. (2009) con AMALGAM. Demuestran que combinar algoritmos multiobjetivo bajo presupuestos compartidos requiere necesariamente **intercambio periódico de poblaciones élites**.
4. **Energy-Aware MO-JSSP:** Salido et al. (2016), Mansouri et al. (2016), May et al. (2015). Formalizan el conflicto Makespan vs Energía con velocidad variable en entornos de manufactura.

---

# 38. Novelty Analysis

* **Aportes Originales de la Tesis:**
  1. Primer estudio sistemático de DMAB con Sliding-Window UCB aplicado al MO-JSSP tri-objetivo con Speed Scaling.
  2. Protocolo estricto de control por Function Evaluations con cero sobrecosto verificado experimentalmente.
  3. Diagnóstico y caracterización transparente del fenómeno del algoritmo dominante en portafolios estancos sin migración.

---

# 39. What If Portfolio Loses?

**Estrategia Científica ante la Victoria de NSGA-II:**
1. **Aceptar y reportar el resultado con total transparencia:** En ciencia, un resultado negativo rigurosamente explicado tiene un valor metodológico incalculable.
2. **Explicar la causa teórica:** La fragmentación del presupuesto y el costo de inicialización múltiple penalizan al portafolio cuando uno de sus brazos es estrictamente superior en velocidad de convergencia.
3. **Resaltar los logros del portafolio:**
   * El portafolio supera con contundencia a 2 de los 3 brazos (MOPSO y NSGA-II+LS).
   * DMAB supera a la asignación uniforme fija (F8.6.2).
   * El portafolio actúa como una red de seguridad (*hedging*) que evita el colapso de rendimiento si un usuario selecciona a ciegas un algoritmo deficiente como MOPSO.

---

# 40. Minimum Viable Thesis

El alcance mínimo para defender con honores la tesis actual requiere:
1. Realizar el análisis estadístico formal (Friedman, Wilcoxon, Holm, $A_{12}$) de los datos ya generados en F8.6.5.
2. Analizar las correlaciones de Spearman entre las características de las instancias y las decisiones de DMAB.
3. Redactar los capítulos de metodología, resultados y discusión analizando con honestidad el comportamiento del portafolio.

---

# 41. Stronger Thesis Option

Para elevar el nivel de la tesis a publicación científica de impacto internacional:
* Añadir una fase experimental breve (F8.6.7 / F8.7) implementando:
  1. Recompensa escalada en DMAB para demostrar que UCB puede converger a explotar a NSGA-II cuando $c$ se calibra adecuadamente.
  2. *Shared Archive Injection* (reinyección de élites en los brazos) para verificar si la cooperación permite que el portafolio supere finalmente a NSGA-II standalone.

---

# 42. Ambitious Thesis Option

* Sustituir MOPSO por **MOEA/D**.
* Implementar selección dinámica de operadores (AOS) dentro de los brazos.
* Evaluar escalamiento hasta 5,000 FE en instancias complejas.
*(Recomendado para una tesis de maestría o proyecto de doctorado posterior).*

---

# 43. Recommended Roadmap

```text
[FASE ACTUAL: F8.6.5 Finalizada y Auditada]
         │
         ▼
[FASE F8.6.6 — Análisis Estadístico Formal e Interpretación]  (P0 - Inmediato)
  - Procesamiento de los CSVs existentes (runs, dmab_blocks, pairwise, summary).
  - Pruebas no paramétricas: Friedman, Wilcoxon Signed-Rank con Holm-Bonferroni.
  - Vargha-Delaney A12 y correlación de Spearman con factores de F8.6.4.
  - Generación de tablas y figuras para la tesis.
         │
         ▼
[FASE F8.6.7 — Diagnóstico de Calibración de DMAB]  (P1 - Recomendado)
  - Prueba focalizada de sensibilidad de c escalado en 5 instancias representativas.
         │
         ▼
[FASE F8.7 — Experimento de Portafolio Cooperativo]  (P2 - Opcional)
  - Prueba de concepto de Shared Archive Injection.
         │
         ▼
[FASE F9 — Redacción Final del Documento de Tesis]  (P0)
  - Redacción integral de los capítulos 3, 4, 5 y 6.
```

---

# 44. Priority Matrix

| Prioridad | Tarea | Justificación |
| :---: | :--- | :--- |
| **P0** | Análisis estadístico formal no paramétrico de F8.6.5 | Indispensable para validar los resultados de la tesis. |
| **P0** | Redacción del diagnóstico riguroso de por qué NSGA-II superó al portafolio | Responde con solidez ante los jurados y revisores. |
| **P1** | Análisis de correlación entre características estructurales y decisiones de DMAB | Demuestra la adaptabilidad según el tipo de instancia. |
| **P2** | Experimento focalizado con reward normalizado / $c$ calibrado en DMAB | Demuestra la capacidad de explotación de DMAB. |
| **P3** | Prueba de concepto de Shared Archive Injection | Opcional para explorar cooperación entre brazos. |
| **P4** | Implementación de MOEA/D o solvers exactos como brazos | Fuera de alcance para la tesis actual. |

---

# 45. Decision Log

* **Decisión 1 (Cerrada):** Mantener el modelo tri-objetivo $(C_{max}, T, E)$ y su evaluación en espacio de Pareto sin agregación escalar.
* **Decisión 2 (Cerrada):** Mantener la contabilidad de presupuesto estricta por Function Evaluations (FE) con cero overshoot.
* **Decisión 3 (Cerrada):** Mantener la normalización analítica y el punto de referencia $r = (1.1, 1.1, 1.1)$.
* **Decisión 4 (Cerrada):** No manipular datos ni semillas para forzar la victoria del portafolio.
* **Decisión 5 (Abierta):** Re-calibrar el parámetro $c$ en DMAB o implementar reward normalizado para futuras fases experimentales.

---

# 46. Open Questions

1. ¿El jurado considerará satisfactoria la demostración de adaptabilidad en F8.6.2 (DMAB > Uniform) y la superioridad frente a 2 de los 3 brazos, o exigirá que el portafolio supere al mejor algoritmo individual?
2. ¿Conviene incorporar un experimento de *Shared Archive Injection* antes de cerrar la etapa experimental?

---

# 47. Final Checklist

- [x] Modelo formal MO-JSSP con Speed Scaling validado.
- [x] Decodificador determinista $O(N)$ y evaluador puro sin fugas.
- [x] Suite de 312 pruebas automáticas en verde (0 fallos).
- [x] Conjunto de 37 instancias formalmente caracterizado en diversidad.
- [x] Experimento principal F8.6.5 ejecutado al 100% (1,480 corridas a 1,000 FE exactas, 0 overshoot).
- [x] Trazabilidad completa de bloques de DMAB registrada en CSV.
- [ ] Análisis estadístico formal (Friedman, Wilcoxon, Holm, $A_{12}$) completado.
- [ ] Gráficos de convergencia y boxplots pareados generados para la tesis.
- [ ] Redacción final del documento de tesis.

---

# MI DIAGNÓSTICO DEL PROYECTO

Respondiendo de forma directa, rigurosa y transparente a las 15 preguntas planteadas para la auditoría:

### 1. ¿Dónde estamos?
Estamos en un estado de **madurez técnica absoluta de ingeniería de software e integridad experimental**. Contamos con un dataset de 1,480 ejecuciones rigurosamente controladas sobre 37 instancias diversas, con presupuesto exacto por Function Evaluations y cero overshoot. El proyecto cuenta con toda la evidencia necesaria para respaldar una tesis honesta, sólida y metodológicamente impecable.

### 2. ¿Qué está sólido?
* El modelo matemático del MO-JSSP con Speed Scaling y tres objetivos independientes.
* La arquitectura de software modular en Python (`src/mojssp/*`) y su suite de 312 tests automáticos con 0 fallos.
* La contabilidad estricta de Function Evaluations reales sin sobrecosto.
* El decodificador serial determinista y el evaluador puro.
* El cálculo exacto 3D de Hypervolume y la normalización analítica con punto de referencia fijo $(1.1, 1.1, 1.1)$.
* La cobertura factorial del benchmark de 37 instancias.

### 3. ¿Qué está débil?
* **El desempeño competitivo del portafolio frente a NSGA-II:** El portafolio pierde contra NSGA-II en las 37 instancias del benchmark bajo 1,000 FE.
* **La calibración del factor de exploración de UCB:** El parámetro $c=0.07$ es excesivamente grande frente a la escala de las recompensas reales ($\Delta HV pprox 0.0042$), lo que anuló la explotación y forzó a DMAB a una asignación cuasi-uniforme.
* **La complementariedad de los brazos:** MOPSO y NSGA-II+LS no aportan diversidad fenotípica bajo presupuestos cortos; son variantes significativamente más lentas que NSGA-II.
* **El aislamiento de los brazos:** La falta de comunicación o migración entre los algoritmos impide que el portafolio aproveche sinergias colectivas.

### 4. ¿Qué falta?
* El procesamiento y análisis estadístico formal no paramétrico (Friedman, Wilcoxon pareado con Holm-Bonferroni, Vargha-Delaney $A_{12}$) de los resultados de F8.6.5.
* La correlación formal entre los descriptores factoriales de las instancias y las asignaciones presupuestarias de DMAB.
* La redacción estructurada de los capítulos de la tesis.

### 5. ¿Qué decisiones debemos mantener?
* La formulación tri-objetivo $(C_{max}, T, E)$ y su no ponderación escalar.
* La representación de Bierwirth con vector de modos canónico.
* El decodificador serial semi-activo determinista.
* La contabilidad de presupuesto estricta por llamadas a `Evaluator.evaluate`.
* El punto de referencia $r = (1.1, 1.1, 1.1)$ y la normalización analítica de cotas fijas.
* El protocolo de warm-up neutral determinista.

### 6. ¿Qué decisiones debemos reabrir o discutir?
* **El hiperparámetro $c$ de DMAB:** Debe reducirse o reemplazarse por una formulación de recompensa auto-normalizada dinámicamente.
* **El aislamiento de los brazos:** Evaluar si se permite la reinyección de élites desde el Global Archive (*Shared Archive Injection*).
* **Los parámetros de MOPSO y Local Search:** Reducir el tamaño de enjambre de MOPSO y el número de vecinos evaluados por LS para evitar el despilfarro de evaluaciones en horizontes acotados.

### 7. ¿Qué experimentos debemos hacer?
1. **Inmediato (F8.6.6):** Procesamiento estadístico formal de los datos ya generados en F8.6.5 (Friedman, Wilcoxon, Holm, $A_{12}$).
2. **Recomendado (F8.6.7):** Prueba de concepto de calibración de $c$ / reward escalado en 5 instancias representativas para corroborar que DMAB es capaz de explotar a NSGA-II.
3. **Ampliación (F8.7):** Prueba piloto de *Shared Archive Injection* para evaluar si la cooperación supera a NSGA-II standalone.

### 8. ¿Qué algoritmos deberíamos considerar a futuro?
* **MOEA/D:** Por su enfoque ortogonal de descomposición por vectores de peso, es el algoritmo con mayor potencial para complementar verdaderamente a NSGA-II.
* **Pareto Local Search (PLS) acotado:** Como reemplazo de la búsqueda local genérica en NSGA-II+LS.

### 9. ¿Qué debemos hacer si Portfolio < Best Individual?
**Aceptar el resultado con total honestidad científica y convertirlo en el eje analítico de la discusión.** En investigación, demostrar empíricamente los límites de una arquitectura es un aporte fundamental. Se debe:
* Documentar con transparencia la victoria de NSGA-II en F8.6.5.
* Analizar la causa matemática: la interacción entre la escala del reward, la fórmula de UCB y el costo de convergencia interrumpida en poblaciones genéticas.
* Resaltar que el portafolio supera contundentemente a 2 de los 3 brazos (MOPSO y NSGA-II+LS) y que DMAB supera a la asignación uniforme fija (F8.6.2).
* Presentar la tesis como la caracterización del *trade-off* entre adaptabilidad, overhead computacional y profundidad de búsqueda en metaheurísticas multiobjetivo.

### 10. ¿Cómo demostrar eficiencia?
Demostrando que el portafolio alcanza soluciones de alta calidad con un overhead computacional de decisión despreciable ($<0.1\%$ del tiempo de CPU) y evaluando la tasa de acumulación de Hypervolume por unidad de FE ($AUC_{HV}$).

### 11. ¿Cómo demostrar adaptabilidad?
Demostrando que:
1. En F8.6.2, DMAB asigna más presupuesto al mejor algoritmo que una política estática, superándola con significancia estadística.
2. La asignación de bloques varía de forma no aleatoria a lo largo de las fases de ejecución (dinamismo temporal).
3. Existen diferencias en la asignación de brazos según las características de las instancias (presión de tardiness vs conflicto energético).

### 12. ¿Qué evidencia necesitamos para responder la pregunta de investigación?
La evidencia ya está en los datasets generados:
* Para la pregunta de *implementabilidad y eficiencia:* La arquitectura modular, el control estricto de FE y el análisis de tiempos y sobrecostos.
* Para la pregunta de *adaptabilidad:* Los registros bloque a bloque de DMAB (`f865_dmab_blocks.csv`) y la comparación pareada contra la política uniforme (`f86_adaptive_vs_uniform.csv`).
* Para la pregunta de *desempeño:* El ranking de configuraciones y la discusión crítica de las limitaciones del portafolio estanco bajo presupuestos reducidos.

### 13. ¿Cuál sería el camino mínimo para terminar la tesis?
1. Ejecutar el análisis estadístico de F8.6.5.
2. Elaborar las tablas y gráficos de resultados (boxplots pareados, trayectorias de bloques de DMAB, curvas de convergencia).
3. Redactar la tesis estructurando el análisis del portafolio con enfoque crítico y transparente.

### 14. ¿Cuál sería el camino para hacerla significativamente más fuerte?
Añadir una fase experimental breve (F8.7) con **Shared Archive Injection** en un subconjunto representativo de 10 instancias, mostrando la transición de un "portafolio estanco" (que pierde) a un "portafolio cooperativo" (que aprovecha sinergias y compite cara a cara con NSGA-II).

### 15. ¿Qué NO deberíamos hacer?
* **NO alterar el código de evaluación ni manipular semillas para intentar hacer ganar al portafolio.**
* **NO agregar algoritmos exactos como brazos en línea bajo presupuesto de FE.**
* **NO redefinir los tres objetivos en una suma ponderada.**
* **NO descartar instancias complejas para mejorar los promedios.**
* **NO cambiar el protocolo experimental cerrado sin una justificación matemática explícita.**
