# Estado de Git, Control de Versiones y Propuesta de Congelación

Este documento detalla el estado del control de versiones Git al momento del cierre formal de la Fase 2, audita los cambios pendientes y formula una propuesta estructurada de commits y tag para congelar la línea base experimental de cara a la Fase 3.

---

## 1. Inspección del Estado Actual de Git

- **Rama activa:** `feature/alg-comparison-moead-spea2`
- **Último commit confirmado (HEAD):** `a5566d4` (*results(pilot): persist pilot experimental datasets, diagnostics, and plots*)

### A. Archivos modificados bajo seguimiento (`git status -s`)
Cuatro archivos del paquete `src/mojssp/` presentan modificaciones respecto a HEAD:

1. `src/mojssp/__init__.py`:
   - Exportación pública de `RoundRobinSelector` y `run_phase2_portfolio_experiment`.
2. `src/mojssp/dmab.py`:
   - Implementación de `RoundRobinSelector` (selector determinista cíclico uniforme conforme al protocolo `DMABSelector`).
   - Implementación de `UniformRandomSelector`.
   - Soporte para protocolos de inicio equivalente (`initialize_arm`, `is_arm_initialized`, `is_in_initial_probe`).
3. `src/mojssp/portfolio.py`:
   - Registro de alias canónicos para MOEA/D (`moead`, `moea_d`, `moea/d`, `moea-d`) y SPEA2 (`spea2`, `spea_2`, `spea-2`, `speaii`).
4. `src/mojssp/runner.py`:
   - Implementación de `run_phase2_portfolio_experiment`: orquestador desacoplado para experimentos de 3 brazos con soporte para políticas `adaptive` y `uniform`, derivación determinista de semillas pseudoaleatorias independientes para cada algoritmo y registro de checkpoints.
   - Parámetro `max_generations=None` en la invocación de `NSGA2Arm` (en `run_standalone_experiment` y `run_phase2_portfolio_experiment`), indispensable para evitar la terminación prematura en 1.530 evaluaciones bajo presupuestos $\ge 3.000$ FE.

### B. Inventario de archivos sin seguimiento (`untracked`)
Se identificaron las siguientes rutas no versionadas:
- **Resultados de Fase 2 a versionar:**
  - `results/expanded_portfolio_phase2/pilot/` (150 corridas del piloto F2.4).
  - `results/expanded_portfolio_phase2/budget_diagnostic/` (450 registros de hitos de presupuesto F2.5.1).
  - `results/expanded_portfolio_phase2/closure_audit/` (tablas de auditoría F2.5.2).
  - `results/expanded_portfolio_phase2/final_closure/` (informes y manifiestos de cierre F2.6).
- **Scripts de reproducibilidad de Fase 2 a versionar:**
  - `scripts/run_phase2_pilot.py`
  - `scripts/run_phase2_budget_diagnostic.py`
  - `scripts/analyze_phase2_pilot.py`
  - `scripts/analyze_phase2_budget_diagnostic.py`
  - `scripts/audit_phase2_closure.py`
- **Pruebas de integración de Fase 2 a versionar:**
  - `tests/test_phase2_portfolio_integration.py`
- **Archivos de Fase 1 / Auxiliares existentes:**
  - `results/expanded_complementarity_phase1/`
  - `scripts/run_phase1_complementarity.py`, `scripts/analyze_phase1_closure.py`
  - `tests/test_complementarity_phase1.py`, `tests/test_instance_pairing.py`
  - `src/mojssp/pairing.py`

### C. Verificación de exclusión de datos holdout y temporales
Se verificó expresamente que:
- **No se incluyen archivos del conjunto de prueba holdout:** Las instancias de `data/generated/expanded_200/holdout_test` permanecen intactas y no fueron referenciadas en ningún script ni resultado de la Fase 2.
- **No se incluyen archivos temporales ni artefactos de chat:** No se registran archivos `.tmp`, caches ni artefactos volátiles en los directorios de código ni de resultados de producción.

---

## 2. Auditoría Técnica de la Suite de Pruebas

Se ejecutó la suite completa de pruebas unitarias e integrales del repositorio mediante el módulo estándar `unittest`:

```text
python -m unittest discover tests
....................................................................................................
Ran 375 tests in 15.738s
OK
```

**Resultado:** **375 pruebas ejecutadas, 375 aprobadas, 0 fallos, 0 errores.**

---

## 3. Propuesta Estructurada de Commits y Tag de Cierre

De acuerdo con las restricciones obligatorias, **no se ha ejecutado ningún commit, tag ni cambio de rama**. Se presenta la secuencia exacta propuesta para que el usuario congele la Fase 2 cuando lo considere oportuno:

### Commit 1: `feat(portfolio): integrate 3-arm portfolio with SW-UCB and Round-Robin selectors`
- **Ámbito:** Código de producción y pruebas unitarias de integración de Fase 2.
- **Archivos a incluir:**
  ```text
  src/mojssp/__init__.py
  src/mojssp/dmab.py
  src/mojssp/portfolio.py
  src/mojssp/runner.py
  tests/test_phase2_portfolio_integration.py
  ```
- **Mensaje propuesto:**
  ```text
  feat(portfolio): integrate 3-arm portfolio with SW-UCB and Round-Robin selectors

  - Add RoundRobinSelector conforming to DMABSelector protocol for uniform baseline.
  - Implement run_phase2_portfolio_experiment supporting adaptive and uniform policies.
  - Configure max_generations=None in NSGA2Arm to allow evaluation budgets > 1500 FE.
  - Add canonical aliases for MOEA/D and SPEA2 arms.
  - Add comprehensive unit and integration tests (375 tests passing).
  ```

### Commit 2: `feat(scripts): add phase 2 experimental runners and audit tools`
- **Ámbito:** Scripts de ejecución, diagnóstico y auditoría de la Fase 2.
- **Archivos a incluir:**
  ```text
  scripts/run_phase2_pilot.py
  scripts/run_phase2_budget_diagnostic.py
  scripts/analyze_phase2_pilot.py
  scripts/analyze_phase2_budget_diagnostic.py
  scripts/audit_phase2_closure.py
  ```
- **Mensaje propuesto:**
  ```text
  feat(scripts): add phase 2 experimental runners and audit tools

  - Add runners for F2.4 pilot (1000 FE) and F2.5.1 budget diagnostic (1000, 3000, 5000 FE).
  - Add statistical and adaptation audit scripts implementing hierarchical aggregation.
  ```

### Commit 3: `docs(phase2): record closure audit, validation report, and reproducibility manifest`
- **Ámbito:** Datasets experimentales de Fase 2, informes de validación y manifiesto de cierre.
- **Archivos a incluir:**
  ```text
  results/expanded_portfolio_phase2/pilot/
  results/expanded_portfolio_phase2/budget_diagnostic/
  results/expanded_portfolio_phase2/closure_audit/
  results/expanded_portfolio_phase2/final_closure/
  ```
- **Mensaje propuesto:**
  ```text
  docs(phase2): record closure audit, validation report, and reproducibility manifest

  - Add formal scientific closure report and validation findings for Phase 2.
  - Include reproducibility manifest freezing baseline parameters for Phase 3.
  - Record claims matrix correcting methodological statements.
  - Issue official Phase 2 closure verdict: CIERRE APROBADO.
  ```

### Tag propuesto: `v0.2.0-phase2-closure`
- **Comando propuesto:**
  ```bash
  git tag -a v0.2.0-phase2-closure -m "Formal closure of Phase 2: 3-arm adaptive portfolio baseline frozen"
  ```
