# Informe de Validación Crítica de la Auditoría Pareto (P3.5)

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Autor:** Antigravity (Auditoría Técnica Independiente)  
**Fecha:** 2026-10-15  
**Entorno de Trabajo:** Worktree Aislado `mojssp-pareto-cooperation` (Rama `experiment/pareto-archive-cooperation`, Commit `ea044c0`)

---

## 1. Validación de la Complementariedad Calculada

Se realizó una revisión minuciosa de `complementarity_metrics.csv` y de los scripts fuente de la Fase 2 (`audit_phase2_closure.py` y `budget_fronts.jsonl`):

### 1.1. Correspondencia Estructural de las Corridas
- **Estructura de Casos:** Se confirmó que los 90 casos corresponden estrictamente a 10 bases independientes del split de desarrollo (`base_c01_5x5_b03` a `base_c08_50x50_b03`) $\times$ 3 semillas maestras (`42`, `43`, `44`) $\times$ 3 presupuestos de evaluación ($1.000$, $3.000$ y $5.000$ FE).
- **Tratamiento de Checkpoints:** Se verificó que los 15.000 registros en `budget_checkpoints.csv` pertenecen a las trayectorias longitudinales de las 150 ejecuciones de $B=5.000$ FE. En ningún caso se trataron como muestras independientes; las pruebas estadísticas se computaron exclusivamente sobre las 10 bases al término de la corrida.
- **Identificación de Algoritmos:** Las 450 corridas en `budget_runs.csv` están inequívocamente etiquetadas con sus algoritmos y protocolos (`MOEA/D`, `NSGA-II`, `SPEA2`, `Uniform Portfolio (Round-Robin)` y `Adaptive Portfolio (DMAB)`).

### 1.2. Explicación Rigurosa de los Cero Vectores Objetivos Compartidos
Uno de los resultados más llamativos de la auditoría preliminar fue que el número de soluciones compartidas en el frente de unión era exactamente cero (`shared_solutions == 0`) en los 90 casos. Se investigó a fondo este fenómeno mediante análisis empírico directo sobre los frentes:
1. **Definición de Igualdad Empleada:** La igualdad utilizada en `audit_phase2_closure.py` fue la **igualdad estricta de tupla** `(Cmax, T, E)_1 == (Cmax, T, E)_2` sobre números de punto flotante de precisión doble (`float64`).
2. **Espacio Combinatorio Discreto Subyacente:** Aunque los objetivos se almacenan como `float` (ej. `252.0`, `146.0`, `1683.0`), son valores discretos exactos derivados de duraciones y consumos de energía enteros. En una instancia representativa ($5 \times 5$, 25 operaciones), el makespan varía en $[252, 410]$ (158 valores), la tardanza en $[122, 781]$ (660 valores) y la energía en $[1076, 1683]$ (608 valores), conformando una malla combinatoria de más de $6.3 \times 10^7$ posibles ternas enteras.
3. **Flujos Aleatorios Ortogonales:** En `runner.py` (líneas 415–417), cada algoritmo se inicializa con una semilla pseudoaleatoria independiente derivada deterministamente:
   $$\text{seed}_{\text{moead}} \ne \text{seed}_{\text{nsga2}} \ne \text{seed}_{\text{spea2}}$$
   Cada algoritmo inicia con poblaciones iniciales distintas y opera con paradigmas de búsqueda ortogonales (descomposición Tchebycheff vs torneo/crowding vs fitness de fuerza/k-NN).
4. **Distancia Mínima en el Espacio Objetivo:** Se calculó la distancia euclidiana mínima entre cualquier solución de un algoritmo y cualquier solución de otro:
   - $\min d(\text{MOEA/D}, \text{NSGA-II}) = 11.045$
   - $\min d(\text{MOEA/D}, \text{SPEA2}) = 11.576$
   - $\min d(\text{NSGA-II}, \text{SPEA2}) = 7.550$
   Los algoritmos coinciden ocasionalmente en una coordenada individual (ej. mismo $C_{max}$ o misma energía), pero **nunca en las tres coordenadas simultáneamente**. Por tanto, la ausencia de vectores compartidos no es un error de cálculo ni un artefacto de redondeo, sino una propiedad genuina de la exploración estocástica en un espacio combinatorio 3D con presupuestos de 1.000 a 5.000 evaluaciones.

---

## 2. Validación de las Propiedades del Archivo y Flujo de Soluciones

Se ejecutaron pruebas deterministas en memoria utilizando la instancia `data/validation/small_3x2.dzn` y se inspeccionó el código fuente:

| Propiedad Evaluada | Método de Verificación | Resultado Observado | Estado |
| :--- | :--- | :--- | :--- |
| **Ausencia de Rutas de Fuga** | Inspección de todas las llamadas a `_evaluator.evaluate()` y `_decoder.decode()` en `arms.py`, `moead.py` y `spea2.py`. | En los tres brazos, la función interna de evaluación invoca inmediatamente `_archive.add(sol, sched, objs)`. No existe ninguna llamada de evaluación huérfana. | **DEMOSTRADO POR CÓDIGO Y PRUEBA** |
| **Entrega al Portafolio** | Ejecución de bloque controlado de 25 FE en cada brazo. | Al finalizar el bloque, `arm.run(budget)` retorna `AlgorithmBlockResult` con un snapshot defensivo del archivo acumulado (`_get_archive_snapshot()`). | **DEMOSTRADO POR PRUEBA DETERMINISTA** |
| **Empates Objetivos con Distinto Genotipo** | Inserción en `ParetoArchive` de dos genotipos distintos con idéntico vector $(10, 0, 5.0)$. | El archivo contiene ambas soluciones (`len(archive) == 2`). Ninguna domina a la otra; ambas se preservan para mantener diversidad estructural. | **DEMOSTRADO POR PRUEBA DETERMINISTA** |
| **Rechazo de Genotipos Duplicados** | Inserción repetida del mismo genotipo idéntico. | `ParetoArchive.add()` retorna `False` y no duplica la entrada en el archivo. | **DEMOSTRADO POR PRUEBA DETERMINISTA** |
| **Inmutabilidad de Soluciones Almacenadas** | Intento de mutar atributos en `Solution`, `Schedule` y `ArchiveEntry`. | Todas las clases están decoradas con `@dataclass(frozen=True)` y sus atributos son tuplas inmutables. El intento de asignación genera `FrozenInstanceError`. | **DEMOSTRADO POR PRUEBA DETERMINISTA** |

---

## 3. Corrección Crítica en la Fórmula de Contribución Marginal ($MC_i$)

Durante la auditoría de `scripts/audit_phase2_closure.py` (líneas 377–389), se detectó una discrepancia conceptual entre el código implementado y la definición matemática formal:

### 3.1. Fórmula Implementada en Fase 2 vs Fórmula Canónica
- **Implementación en Fase 2 (`audit_phase2_closure.py`):**
  ```python
  union_minus_m = [p for p in union_nd if p not in m_pts]
  hv_minus_m = compute_hypervolume(union_minus_m)
  mc_m = hv_total_union - hv_minus_m
  ```
  Esta fórmula simplemente elimina las soluciones de MOEA/D del frente de unión **ya filtrado** $U$.
- **Fórmula Matemática Canónica:**
  $$MC_i^{\text{canonical}} = HV(U) - HV\left(ND\left(\bigcup_{j \ne i} A_j\right)\right)$$
  Al retirar a MOEA/D de la competencia, las soluciones de NSGA-II o SPEA2 que fueron dominadas previamente por MOEA/D **deben volver a ser candidatas** al calcular el frente de los algoritmos restantes.

### 3.2. Impacto Cuantitativo de la Corrección
Al aplicar el operador de no dominancia sobre la unión de los otros dos algoritmos ($ND(A_{\text{NSGA-II}} \cup A_{\text{SPEA2}})$):
- Reaparecen entre 11 y 71 puntos de NSGA-II y SPEA2 que habían sido dominados por MOEA/D en el frente global.
- Como consecuencia, el Hypervolume del conjunto restante es mayor:
  $$HV\left(ND\left(\bigcup_{j \ne i} A_j\right)\right) \ge HV(U \setminus A_i)$$
- Por lo tanto, el valor reportado en `complementarity_audit.csv` para la contribución marginal de MOEA/D estaba **sistemáticamente sobreestimado**:
  - En `base_c01_5x5_b03` ($s=42$, $B=1000$):
    - $MC_{\text{MOEA/D}}^{\text{closure}} = 0.181893$
    - $MC_{\text{MOEA/D}}^{\text{canonical}} = 0.077987$ (Sobreestimación: $+0.103906$).
  - En $B=5000$:
    - $MC_{\text{MOEA/D}}^{\text{closure}} = 0.018318$
    - $MC_{\text{MOEA/D}}^{\text{canonical}} = 0.012363$ (Sobreestimación: $+0.005956$).
- **Conclusión de la Corrección:** La complementariedad marginal de MOEA/D sigue siendo estrictamente positiva ($MC > 0$), pero su magnitud real es más moderada de lo que sugerían los informes preliminares de Fase 2.

---

## 4. Revisión del Problema de `mojssp.pairing`

Se completó el diagnóstico sobre la importación huérfana:

1. **Causa Raíz:** En el commit `473908a`, se modificó `src/mojssp/__init__.py` para exportar símbolos de generación y validación de pares de instancias (`validate_pairing`, etc.), pero el archivo `src/mojssp/pairing.py` se omitió en el comando `git add` y quedó como archivo sin seguimiento en la copia de trabajo local.
2. **Módulos y Pruebas Afectadas:**
   - Ningún algoritmo (`moead.py`, `nsga2.py`, `spea2.py`), ni el orquestador (`orchestrator.py`), ni el evaluador (`evaluator.py`), ni el cálculo de Hypervolume dependen de `pairing.py`.
   - Únicamente fallan `import mojssp` a nivel raíz y las pruebas unitarias que importan el paquete completo.
3. **Uso de Stubs en Auditorías:**
   - La auditoría P1–P3 utilizó un stub en memoria inyectado en `sys.modules['mojssp.pairing']` para scripts interactivos, sin tocar ningún archivo en disco.
4. **Propuesta de Corrección Mínima (Pendiente de Autorización):**
   - En lugar de copiar archivos del repositorio original, la solución más limpia y defensiva dentro del código de producción de este worktree sería envolver la importación en `src/mojssp/__init__.py`:
     ```python
     try:
         from .pairing import (...)
     except ImportError:
         pass
     ```
   - Esta corrección no se ha implementado, en estricto cumplimiento de las restricciones.

---

## 5. Revisión de la Recomendación de Cooperación: Ruta A vs Ruta B

Es fundamental deslindar dos objetivos de investigación distintos:

```text
Ruta A: Diagnóstico de Procedencia No Invasivo (Estudio Pasivo)
Objetivo: Medir cuántas soluciones del archivo global fueron descubiertas por cada brazo
          en el portafolio pasivo actual, sin alterar el comportamiento de los algoritmos.
Complejidad: MÍNIMA (0 cambios en algoritmos, 0 riesgos de convergencia prematura).

Ruta B: Cooperación Activa (Transferencia de Soluciones)
Objetivo: Inyectar soluciones del archivo global o de otros brazos en las poblaciones vivas.
Complejidad: ALTA (requiere mapeo Tchebycheff para MOEA/D, control de diversidad en NSGA-II/SPEA2,
             modificación de contratos de brazos).
```

### 5.1. Factibilidad de la Ruta A sin Modificar Algoritmos
- Para medir la complementariedad interna del portafolio, **no se necesita cooperación activa ni modificar los algoritmos**.
- Basta con instrumentar externamente el método `Portfolio.run_arm()`:
  - Cuando un brazo retorna `result.solutions`, un observador externo registra en un diccionario:
    $$\text{procedencia}[\text{solution\_id}] = (\text{arm\_name}, \text{block\_idx}, \text{fe\_actual})$$
  - Al finalizar la corrida, se consulta qué soluciones del archivo global final sobrevivieron y a qué algoritmo pertenecieron.
- Esto proporciona respuestas empíricas completas a las preguntas de complementariedad interna sin alterar en absoluto la dinámica evolutiva.

---

## 6. Síntesis y Recomendación Concreta para P4

### 1. Resultados Confirmados
- Aislamiento perfecto entre worktrees (`mojssp-dmab` intacto, HEAD en `ea044c0`).
- Integridad y no-fuga de soluciones en los tres brazos (100% de evaluadas se archivan).
- Monotonía estricta y correspondencia del cálculo de Hypervolume final con el archivo global acumulado.
- Immutabilidad estricta de genotipos y fenotipos almacenados.
- Preservación de soluciones no dominadas con objetivos idénticos y genotipos distintos.
- Distancia euclidiana mínima entre frentes de diferentes algoritmos siempre $> 7.5$ unidades.

### 2. Resultados Corregidos
- **Sobreestimación de Contribuciones Marginales:** Se corrigió el sesgo de la fórmula de Fase 2. La contribución marginal canónica $MC_i = HV(U) - HV(ND(\bigcup_{j \ne i} A_j))$ es menor que la reportada en `complementarity_audit.csv`, debido a la recuperación de soluciones dominadas por el algoritmo eliminado.

### 3. Resultados que Siguen sin Poder Verificarse
- Análisis de secuencias de Bierwirth de campañas pasadas (los JSONL solo tienen objetivos 3D).
- Ejecución de nuevas corridas sobre `expanded_200` (archivos `.dzn` no versionados en `ea044c0`).

### 4. Problemas que Impiden Avanzar
- La importación nativa de `mojssp` requiere el stub o la corrección de `__init__.py`.
- No existe trazabilidad de procedencia en las corridas estándar del portafolio.

### 5. Recomendación Concreta para P4
> **Recomendación para P4:** **Priorizar la Ruta A (Diagnóstico de Procedencia No Invasivo).**  
> Diseñar e implementar un observador de bloques externo en el orquestador/runner que registre el algoritmo de origen y el bloque de descubrimiento de cada solución del archivo global, y ejecutar un experimento piloto controlado (10 instancias, 1 semilla, 1.000 FE) sobre el portafolio pasivo actual. Esto permitirá cuantificar la complementariedad real dentro del portafolio **antes** de considerar cualquier modificación invasiva de transferencia poblacional (Ruta B).
