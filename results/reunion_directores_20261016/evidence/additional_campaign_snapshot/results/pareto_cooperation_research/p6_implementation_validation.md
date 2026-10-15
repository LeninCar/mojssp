# Informe de Implementación y Validación Técnica: Cooperación Activa (P6)

**Fecha:** 2026-10-15  
**Worktree:** `..\mojssp-pareto-cooperation` (Rama: `experiment/pareto-archive-cooperation`)  
**Estado:** Implementación y validación completadas. Piloto experimental no iniciado (en espera de autorización).

---

## 1. Resumen de la Implementación Técnica

Se ha implementado el marco de cooperación activa para el portafolio algorítmico MO-JSSP, permitiendo el intercambio controlado de soluciones no dominadas previamente evaluadas entre **MOEA/D, NSGA-II y SPEA2** a través del Archivo Pareto Global, satisfaciendo todas las restricciones de equivalencia, equidad computacional e integridad algorítmica:

1. **Deshabilitada por Defecto:** `CooperativePortfolio` hereda de `ProvenanceObservingPortfolio`. Por defecto (`cooperation_enabled=False`), su comportamiento es **100% idéntico bit a bit** al portafolio pasivo original.
2. **Cero Evaluaciones Adicionales:** Las soluciones inyectadas son tomadas directamente del Archivo Pareto Global (`ArchiveEntry`), conservando sus valores objetivos deterministas $(C_{\max}, T, E)$ y su Schedule fenotípico. No se realiza ninguna llamada adicional a `Evaluator.evaluate()`.
3. **Protección de Arranque (300 FE Intactas):** La inyección activa ocurre exclusivamente a partir del **bloque 6** (`min_cooperation_block=6`), preservando sin perturbación los 3 bloques de calentamiento neutral (150 FE) y los 3 bloques de sondeo inicial obligatorio (150 FE).
4. **Acotamiento y Filtrado:** Se ofrecen como máximo **$\kappa = 2$ soluciones externas por bloque**, seleccionadas deterministamente por extremos de objetivos entre aquellas descubiertas por un brazo diferente al receptor. Los duplicados genotípicos son rechazados antes de alterar el estado del algoritmo.
5. **Observabilidad y Telemetría:** Se registran detalladamente en `InjectionResult` las ofertas, aceptaciones, rechazos por duplicado, rechazos por dominancia/inferioridad, supervivencia en la población al final del bloque y el tiempo de pared consumido por la inyección.

---

## 2. Implementación por Algoritmo

### A. MOEA/D (`MOEADArm.inject_solutions`)
- **Descomposición preservada:** Para cada candidato externo no duplicado, se identifica el subproblema afín $i^* = \arg\min_i g^{te}(f(x_{ext}) \mid \lambda^i, z^*)$.
- **Actualización del punto ideal:** Se actualiza $z^*$ si la solución ofrece una cota inferior no observada.
- **Reemplazo acotado en vecindario:** Se evalúa el vecindario $B(i^*)$ y se sustituye la solución incumbente si y sólo si $g^{te}(f(x_{ext})) < g^{te}(f(x_{sub}))$, respetando el límite `max_replacements`.
- **Invariante:** Cada uno de los $N$ subproblemas conserva su correspondencia `(subproblem_id, weight, neighborhood, solution, objectives)`.

### B. NSGA-II (`NSGA2Arm.inject_solutions`)
- **Tamaño poblacional fijo:** La población $P_t$ se une temporalmente con los candidatos válidos.
- **Criterio canónico de supervivencia:** Se aplica `fast_non_dominated_sort` y `calculate_crowding_distance` sobre la unión, truncando exactamente al tamaño de población $N$.
- **Invariante:** La solución inyectada sólo ingresa si supera o iguala en dominancia/dispersión a los individuos del peor frente de $P_t$, sin sesgar los operadores genéticos posteriores.

### C. SPEA2 (`SPEA2Arm.inject_solutions`)
- **Capacidad de archivo fijo:** Los candidatos válidos se unen al archivo ambiental $\bar{P}_t$.
- **Selección ambiental y truncamiento:** Se recalculan `calculate_spea2_fitness` y `environmental_selection(union, archive_size=K)` con truncamiento determinista lexicográfico.
- **Invariante:** Si la solución inyectada es dominada o incrementa la aglomeración en una región saturada, el truncamiento de SPEA2 la elimina de forma natural.

---

## 3. Resultados de la Suite de Pruebas Automatizadas

Se implementó el archivo [`tests/test_cooperation.py`](file:///C:/Users/lenin/Documents/Ingenier%C3%ADa/2026-1/TG1/mojssp-pareto-cooperation/tests/test_cooperation.py) con 8 pruebas especializadas:

1. `test_cooperative_arm_protocol_conformance`: Valida que los 3 brazos satisfacen formalmente el protocolo `CooperativeArm`.
2. `test_cooperation_disabled_by_default_reproduces_passive`: Valida equivalencia exacta y nulo historial de inyección frente al portafolio pasivo original.
3. `test_zero_evaluations_consumed_during_injection`: Comprueba que `arm.total_evaluations` no se incrementa durante la inyección.
4. `test_rejection_of_identical_genotypes`: Valida rechazo inmediato de soluciones con genotipo ya presente en la población.
5. `test_moead_injection_preserves_subproblem_invariants`: Valida que MOEA/D conserva $N$ subproblemas e incumbentes válidos.
6. `test_nsga2_injection_preserves_population_size`: Valida que NSGA-II conserva exactamente $N$ individuos y calcula distancias válidas.
7. `test_spea2_injection_preserves_archive_size`: Valida que SPEA2 conserva exactamente $K$ individuos en su archivo ambiental.
8. `test_cooperative_portfolio_execution_flow`: Valida la orquestación multialgorítmica en un ciclo de 180 FE con cooperación activa y registro de telemetría.

### Resumen de Ejecución
- **Pruebas ejecutadas:** **369** (361 existentes + 8 nuevas).
- **Aprobadas:** **369 (100%)**.
- **Fallidas:** **0**.
- **Errores:** **0**.
- **Omitidas:** **0**.
- **Tiempo de ejecución:** **20.71 s**.

---

## 4. Inventario de Archivos Modificados y Creados

| Archivo | Estado | Descripción de los Cambios |
| :--- | :---: | :--- |
| `src/mojssp/cooperation.py` | **Nuevo** | Definición del protocolo `CooperativeArm`, dataclasses `ExternalSolutionOffer`, `InjectionResult` y clase `CooperativePortfolio`. |
| `src/mojssp/moead.py` | Modificado | Métodos `inject_solutions` y `get_injected_survivors_count` en `MOEADArm`. |
| `src/mojssp/arms.py` | Modificado | Métodos `inject_solutions` y `get_injected_survivors_count` en `NSGA2Arm`, actualización de imports (`typing.Any`, `Sequence`). |
| `src/mojssp/spea2.py` | Modificado | Métodos `inject_solutions` y `get_injected_survivors_count` en `SPEA2Arm`. |
| `src/mojssp/__init__.py` | Modificado | Exportación de `CooperativeArm`, `CooperativePortfolio`, `ExternalSolutionOffer` e `InjectionResult`. |
| `tests/test_cooperation.py` | **Nuevo** | Suite de 8 pruebas unitarias y de integración para cooperación activa. |
| `results/pareto_cooperation_research/p6_cooperation_design.md` | Existente | Documento formal de diseño metodológico y arquitectónico de P6. |

---

## 5. Limitaciones Metodológicas y Siguientes Pasos

- **Piloto Experimental en Espera:** En cumplimiento estricto de las directrices, **no se ha ejecutado ninguna corrida del piloto experimental de 8 ejecuciones**.
- **Control de Git:** No se han realizado commits, merges, push ni cherry-picks. Todo el código permanece local en el worktree `..\mojssp-pareto-cooperation`.
- **Integridad del Repositorio Original:** El repositorio original `..\mojssp-dmab` permanece completamente intacto.

