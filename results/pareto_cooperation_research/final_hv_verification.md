# Verificación Formal del Cálculo de Hypervolume (HV)

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Módulo Auditado:** Cálculo de Hypervolume en Recompensas, Checkpoints y Resultado Final  
**Fecha:** 2026-10-15  
**Entorno:** `mojssp-pareto-cooperation` (Commit `ea044c0`)

---

## 1. Localización del Cálculo de Hypervolume en la Arquitectura

Se auditó la correspondencia y consistencia del cálculo del Hypervolume en los tres puntos críticos del sistema:

### 1.1. Recompensas del Selector (DMAB)
- **Ubicación:** [`AdaptivePortfolioOrchestrator.step()`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/orchestrator.py#L183-L187) y [`HypervolumeRewardTracker.compute_reward()`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/reward.py#L90-L135).
- **Entrada:** `self._portfolio.global_archive` (el archivo global acumulado).
- **Operación:**
  ```python
  hv_before = self._reward_tracker.current_hv
  reward = self._reward_tracker.compute_reward(self._portfolio.global_archive)
  hv_after = self._reward_tracker.current_hv
  ```
- **Fórmula de recompensa:**
  $$r_t = \max\left(0, HV(A_t) - HV(A_{t-1})\right) = \Delta HV_t$$

### 1.2. Checkpoints de Progreso
- **Ubicación:** [`run_portfolio_experiment()`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/runner.py#L326-L330) y [`run_phase2_portfolio_experiment()`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/runner.py#L487-L492).
- **Lógica:**
  ```python
  checkpoints: List[Tuple[int, float]] = []
  cum_evals = 0
  for b in history:
      cum_evals += b.evaluations_used
      checkpoints.append((cum_evals, b.hv_after))
  ```
- **Comprobación:** Cada punto del checkpoint $(FE, HV)$ registra el $HV(A_t)$ del archivo global acumulado al término de dicho bloque, garantizando la trazabilidad temporal del portafolio.

### 1.3. Resultado Final del Runner
- **Ubicación:** [`runner.py#L332-L356`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/runner.py#L332-L356):
  ```python
  final_archive = portfolio.global_archive
  final_hv = reward_tracker.current_hv
  front_coords = tuple(
      (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
      for e in final_archive.entries
  )
  ```
- **Comprobación:** El `final_hv` reportado en `RunResult.hypervolume` **corresponde con exactitud al estado final del archivo Pareto global acumulado** y **no** a la población interna del último brazo que se ejecutó.

---

## 2. Comprobación de Propiedades e Invariantes

| Criterio Verificado | Implementación Observada | Estado |
| :--- | :--- | :--- |
| **Fuente de Soluciones** | Todas las consultas de HV en el portafolio usan `portfolio.global_archive`. | **CORRECTO** |
| **Normalización Compartida** | Todas las llamadas utilizan [`ObjectiveNormalizer`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/normalization.py#L1-L100) inicializado con `compute_instance_bounds(instance)`. Mismo rango $[0, 1]^3$ por instancia. | **CORRECTO** |
| **Punto de Referencia Canónico** | Exactamente $(1.1, 1.1, 1.1)$ definido en [`DEFAULT_REFERENCE_POINT`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/hypervolume.py#L10) y configurado en `reward_tracker`. | **CORRECTO** |
| **Filtrado no dominado** | [`compute_hypervolume()`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/hypervolume.py#L67-L120) descarta puntos dominados internamente y puntos fuera de la caja de referencia. | **CORRECTO** |
| **Monotonía Acumulada** | [`HypervolumeRewardTracker`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/reward.py#L121-L134) lanza `RewardInvariantError` si $\Delta HV < -10^{-12}$. | **CORRECTO** |
| **Coincidencia Final** | El valor final reportado en `runs.csv` coincide con el último `hv_after` y con el HV directo de `global_archive`. | **CORRECTO** |

### 2.1. Evidencia Empírica de Monotonía en los Datos de la Fase 2
En la auditoría de cierre de la Fase 2 ([`scripts/audit_phase2_closure.py#L108-L120`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/scripts/audit_phase2_closure.py#L108-L120)):
- Se analizaron los **15.000 checkpoints** de las 150 corridas del diagnóstico de presupuesto (`budget_checkpoints.csv`).
- **Violaciones de monotonía observadas:** **0** (`0 non-monotonic steps observed, PASS`).
- Esto demuestra que la combinación de `ParetoArchive.update()` con `HypervolumeRewardTracker` preserva de manera determinista la propiedad:
  $$HV(A_{t+1}) \ge HV(A_t)$$
  salvo tolerancias de punto flotante acotadas a nivel de máquina ($\le 10^{-12}$).

