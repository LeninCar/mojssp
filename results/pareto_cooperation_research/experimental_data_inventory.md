# Inventario de Datos Experimentales Disponibles y Compatibilidad

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Fecha:** 2026-10-15  
**Entorno:** `mojssp-pareto-cooperation` (Commit `ea044c0`)

---

## 1. Inventario General de Conjuntos de Datos en el Worktree

Se auditó la totalidad de los datos experimentales versionados en Git dentro del commit congelado `ea044c0`.

| Directorio | Contenido | Algoritmos Incluidos | Presupuestos (FE) | Estado de Integridad |
| :--- | :--- | :--- | :--- | :--- |
| `results/expanded_portfolio_phase2/budget_diagnostic/` | 450 corridas completas, 15.000 checkpoints, frentes 3D en JSONL, bloques de portafolio y asignaciones de brazos. | MOEA/D, NSGA-II, SPEA2, Uniform Portfolio, Adaptive Portfolio (DMAB). | 1.000, 3.000, 5.000 | **COMPLETO Y VALIDADO** |
| `results/expanded_portfolio_phase2/pilot/` | 150 corridas del piloto de 3 brazos, frentes 3D en JSONL, bloques y asignaciones. | MOEA/D, NSGA-II, SPEA2, Uniform Portfolio, Adaptive Portfolio (DMAB). | 1.000 | **COMPLETO Y VALIDADO** |
| `results/expanded_portfolio_phase2/closure_audit/` | Auditoría de complementariedad (90 registros), diferencias pareadas por base y resumen estadístico de Wilcoxon. | MOEA/D, NSGA-II, SPEA2, Uniform, DMAB. | 1.000, 3.000, 5.000 | **COMPLETO Y VALIDADO** |
| `results/expanded_portfolio_phase2/final_closure/` | Informes de cierre de Fase 2, matriz de afirmaciones F2.6 y manifiesto de reproducibilidad. | Síntesis metanalítica de los 3 brazos. | N/A | **COMPLETO** |
| `results/raw/` (Histórico Fase 1 / F8.6.5) | Corridas históricas del portafolio inicial (NSGA-II, MOPSO, NSGA-II+LS). | NSGA-II, MOPSO, NSGA-II+LS. | 500 | Incompatible con 3 brazos definitivos. |
| `results/expanded_complementarity_phase1/` | No versionado en Git (estaba sin seguimiento en `mojssp-dmab`). | N/A | N/A | **NO DISPONIBLE EN WORKTREE** |

---

## 2. Ficha Técnica del Conjunto Principal: Diagnóstico de Presupuesto (`budget_diagnostic`)

Este conjunto constituye la fuente empírica fundamental para la auditoría de complementariedad, al contener ejecuciones pareadas idénticas entre los tres algoritmos independientes y las dos variantes de portafolio.

- **Identificadores de Instancia y Bases Independientes (10 bases del split `development`):**
  1. `base_c01_5x5_b03` (Base: `base_c01_5x5_b03`, Perfil: `base`, $5 \times 5$, 25 ops)
  2. `base_c01_5x5_b05_tard_med` (Base: `base_c01_5x5_b05`, Perfil: `tard_med`, $5 \times 5$, 25 ops)
  3. `base_c02_10x10_b03_tard_high` (Base: `base_c02_10x10_b03`, Perfil: `tard_high`, $10 \times 10$, 100 ops)
  4. `base_c02_10x10_b04_nrg_strong` (Base: `base_c02_10x10_b04`, Perfil: `nrg_strong`, $10 \times 10$, 100 ops)
  5. `base_c03_20x10_b04_btnk_high` (Base: `base_c03_20x10_b04`, Perfil: `btnk_high`, $20 \times 10$, 200 ops)
  6. `base_c04_10x20_b04_btnk_high` (Base: `base_c04_10x20_b04`, Perfil: `btnk_high`, $10 \times 20$, 200 ops)
  7. `base_c05_20x20_b03_base` (Base: `base_c05_20x20_b03`, Perfil: `base`, $20 \times 20$, 400 ops)
  8. `base_c06_30x20_b03_base` (Base: `base_c06_30x20_b03`, Perfil: `base`, $30 \times 20$, 600 ops)
  9. `base_c07_40x20_b03_base` (Base: `base_c07_40x20_b03`, Perfil: `base`, $40 \times 20$, 800 ops)
  10. `base_c08_50x50_b03_base` (Base: `base_c08_50x50_b03`, Perfil: `base`, $50 \times 50$, 2500 ops)
- **Semillas Maestras Evaluadas:** `42`, `43`, `44` (3 réplicas pareadas con semillas derivadas por brazo).
- **Presupuestos Computacionales:** $1.000$, $3.000$ y $5.000$ evaluaciones reales (`evaluations_used == budget`, overshoot = 0).
- **Parámetros del Portafolio:**
  - Tamaño de bloque: $B = 50$ FE.
  - Tamaño de población: $N = 30$.
  - Selector adaptativo: Sliding Window UCB ($W = 10$, $c = 0.07$).
  - Warm-up neutral: 1 bloque por brazo (3 bloques iniciales = 150 FE).
- **Normalización y Punto de Referencia:**
  - Normalización min-max basada en cotas analíticas teóricas de la instancia (`compute_instance_bounds`).
  - Punto de referencia en espacio normalizado: exactamente `(1.1, 1.1, 1.1)`.
- **Datos Disponibles por Corrida:**
  - Vectores objetivos 3D: Sí, en `budget_fronts.jsonl` (450 frentes).
  - Checkpoints: Sí, en `budget_checkpoints.csv` (100 checkpoints por corrida para $B=5000$).
  - Asignación de evaluaciones por brazo: Sí, en `budget_arm_allocations.csv`.
  - Trazas de bloques: Sí, en `budget_portfolio_blocks.csv`.
  - Genotipos serializados en disco: **No** (solo vectores objetivo $C_{max}, T, E$).

---

## 3. Matriz de Compatibilidad Metodológica

| Comparación | Compatibilidad | Razón Metodológica |
| :--- | :--- | :--- |
| **MOEA/D vs NSGA-II vs SPEA2 (Standalone)** | **ALTA (100% Compatible)** | Mismas instancias, semillas derivadas, mismo presupuesto FE, idéntico normalizador y referencia HV. |
| **Portafolio (DMAB) vs Portafolio (Uniforme)** | **ALTA (100% Compatible)** | Mismo presupuesto total compartido, mismos bloques ($B=50$), mismo warm-up neutral, mismos brazos. |
| **Portafolio vs Standalone (Mismo Presupuesto B)** | **ALTA (Comparación Justa)** | Ambos consumen exactamente $B$ evaluaciones de `Evaluator.evaluate()`. El portafolio divide su presupuesto entre 3 brazos; el standalone lo asigna al 100% a un único algoritmo. |
| **Unión Retrospectiva vs Portafolio Compartido** | **CONCEPTUALMENTE DISTINTOS** | La unión retrospectiva suma $3 \times B$ evaluaciones (15.000 FE a $B=5000$), mientras que el portafolio compartido solo consume $B$ evaluaciones (5.000 FE). |
| **Datos Fase 2 vs Datos F8.6.5 (MOPSO / NSGA-II+LS)** | **INCOMPATIBLE** | Conjunto de brazos distinto y presupuesto de 500 FE; no deben combinarse. |

