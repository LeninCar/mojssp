# Propuesta de Arquitectura de Observabilidad y Procedencia para P4 (P4-A)

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Autor:** Antigravity (Auditoría Técnica Independiente)  
**Fecha:** 2026-10-15  
**Entorno de Trabajo:** Worktree Aislado `mojssp-pareto-cooperation` (Rama `experiment/pareto-archive-cooperation`, Commit `ea044c0`)

---

## 1. Objetivos del Diseño de Observabilidad

El objetivo de esta propuesta es instrumentar el flujo de soluciones hacia el `Global Pareto Archive` para registrar de manera unívoca la procedencia y el ciclo de vida de cada solución no dominada descubierta durante la ejecución del portafolio pasivo actual, **sin alterar en absoluto**:
- La política de selección adaptativa (Sliding Window UCB).
- El cálculo de recompensas ($\Delta HV$).
- La contabilización estricta de evaluaciones ($B_{\text{total}}$ y $B_{\text{block}}$).
- Los algoritmos de optimización (MOEA/D, NSGA-II, SPEA2).
- El decodificador serial ni la semántica del archivo Pareto global.

---

## 2. Distinción Fundamental: FE de Descubrimiento vs FE de Incorporación

Es imperativo diferenciar temporalmente dos momentos de evaluación:

```text
Bloque k (Presupuesto B = 50 FE)
[FE_global = 150] ──────────────────────────────────────────────> [FE_global = 200]
      │                                                                  │
      ├── FE_local = 12: Solución s_1 generada y evaluada                │
      │   (FE de Descubrimiento = 162)                                   │
      ├── FE_local = 37: Solución s_2 generada y evaluada                │
      │   (FE de Descubrimiento = 187)                                   │
      │                                                                  │
      └─────────────────────────────────────────────────────────> Fin de Bloque k
                                                                  Entrega de Snapshot
                                                                  (FE de Incorporación = 200)
```

1. **FE de Descubrimiento (Discovery FE):**
   - Es la evaluación local específica dentro del bloque en que la solución fue instanciada y evaluada por `Evaluator.evaluate()`.
   - **Limitación Técnica:** En la arquitectura actual, los brazos operan como una "caja negra" durante el bloque (`arm.run(budget)`). No es posible conocer la FE de descubrimiento exacta de cada individuo **sin modificar el bucle interno de los algoritmos** para que etiqueten el contador local al momento de evaluar.
2. **FE de Incorporación al Archivo (Archive Ingestion FE):**
   - Es el número total de evaluaciones globales acumuladas por el portafolio (`portfolio.total_evaluations`) en el momento en que el bloque termina y el snapshot de soluciones se inserta en el archivo global.
   - **Factibilidad:** **100% viable mediante instrumentación externa no invasiva**, sin tocar los algoritmos. Cada solución aceptada en el bloque $k$ queda registrada con `ingestion_fe = portfolio.total_evaluations` y `block_index = k`.

---

## 3. Modelo de Datos y Entidades de Observabilidad

### 3.1. Identificadores Estables
- **Identificador de Genotipo (`genotype_id`):**  
  Hash determinista SHA-256 de la tupla `(solution.sequence, solution.modes)`:
  $$\text{id}_{\text{geno}} = \text{sha256}(\text{repr}(sol.sequence) + \text{repr}(sol.modes))[:16]$$
- **Identificador de Vector Objetivo (`objective_key`):**  
  Tupla inmutable con redondeo de seguridad para punto flotante:
  $$\text{key}_{\text{obj}} = (C_{\text{max}}, T, \text{round}(E, 4))$$

### 3.2. Estructura de Registro por Solución (`SolutionProvenanceRecord`)
```python
@dataclass
class SolutionProvenanceRecord:
    genotype_id: str
    objective_key: Tuple[int, int, float]
    origin_arm: str
    first_seen_block: int
    first_seen_ingestion_fe: int
    discovered_by_arms: Set[str]  # Conjunto de brazos que descubrieron independientemente este genotipo/objetivo
    status: str                   # 'ACTIVE' (actualmente en el archivo) o 'DOMINATED_EVICTED' (eliminada posteriormente)
    evicted_at_block: Optional[int] = None
    evicted_at_fe: Optional[int] = None
    evicted_by_arm: Optional[str] = None
```

### 3.3. Estructura de Registro por Bloque (`BlockProvenanceTrace`)
Para cada bloque $k$ ejecutado:
- `block_index`: int
- `arm_selected`: str
- `budget_allocated`: int
- `evaluations_used`: int
- `ingestion_fe`: int
- `solutions_offered`: int (total de soluciones entregadas por el brazo en su snapshot)
- `solutions_accepted_new`: int (soluciones no dominadas que ingresaron por primera vez al archivo)
- `solutions_duplicate_genotype`: int (soluciones descartadas por genotipo idéntico ya presente)
- `solutions_rejected_dominated`: int (soluciones dominadas por el archivo global existente)
- `solutions_evicted_from_archive`: int (soluciones previamente activas en el archivo que fueron dominadas y expulsadas por las nuevas)
- `hv_before`: float
- `hv_after`: float
- `block_reward_delta_hv`: float

---

## 4. Diseño del Mecanismo No Invasivo: `ProvenanceObservingPortfolio`

Para no modificar [`Portfolio`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/portfolio.py#L33) ni romper su contrato, se propone implementar un contenedor transparente (patrón Wrapper/Decorator o Callback):

```python
class ProvenanceObservingPortfolio(Portfolio):
    """Subclase defensiva que añade telemetría de procedencia a run_arm() sin alterar la lógica de optimización."""

    def __init__(self, arms=None):
        super().__init__(arms=arms)
        self.provenance_registry: Dict[str, SolutionProvenanceRecord] = {}
        self.block_traces: List[BlockProvenanceTrace] = []

    def run_arm(self, name: str, budget: int) -> PortfolioBlockResult:
        # 1. Snapshot del archivo global antes del bloque
        entries_before = set(self._global_archive.entries)
        
        # 2. Ejecución normal del bloque en el algoritmo
        result = super().run_arm(name, budget)
        
        # 3. Snapshot del archivo global después del bloque
        entries_after = set(self._global_archive.entries)
        
        # 4. Cálculo de diferencias de conjuntos:
        new_entries = entries_after - entries_before
        evicted_entries = entries_before - entries_after
        
        # 5. Registro de procedencia de nuevas incorporaciones y expulsiones
        self._record_provenance_events(
            arm_name=result.arm_name,
            new_entries=new_entries,
            evicted_entries=evicted_entries,
            arm_result=result.arm_result,
        )
        return result
```

### Ventajas Arquitectónicas:
1. **Cero invasión en algoritmos:** `NSGA2Arm`, `MOEADArm` y `SPEA2Arm` no requieren ni una sola línea de modificación.
2. **Reversibilidad total:** Si se utiliza `Portfolio` estándar, el sistema se comporta de forma idéntica a la Fase 2.
3. **Preservación de Semillas y Trazas:** Al no consumir llamadas aleatorias ni cambiar el orden de las operaciones, la trayectoria de ejecución es **bit-for-bit idéntica** a la versión sin observabilidad.

---

## 5. Plan de Pruebas Unitarias para P4

Antes de lanzar cualquier prueba con instancias de desarrollo, se implementará la suite `tests/test_provenance_observability.py`:

1. **`test_provenance_tracking_single_block`:** Verificar que las soluciones añadidas en el bloque 0 se etiquetan correctamente con el brazo ejecutor y el bloque 0.
2. **`test_provenance_multiple_arms_tracking`:** Ejecutar 1 bloque de MOEA/D y 1 bloque de NSGA-II; comprobar que las soluciones de cada uno conservan su atribución correcta en el registro.
3. **`test_provenance_eviction_tracking`:** Crear deliberadamente una solución subóptima en el bloque 0 y una dominante en el bloque 1; verificar que la primera pase a estado `'DOMINATED_EVICTED'` con `evicted_by_arm` correctamente anotado.
4. **`test_provenance_multiple_provenance_tie`:** Verificar que si dos algoritmos descubren soluciones con idéntico vector objetivo o genotipo, ambos figuren en `discovered_by_arms`.
5. **`test_bitwise_reproducibility`:** Comprobar que una corrida con `ProvenanceObservingPortfolio` produce exactamente el mismo frente, checkpoints y número de evaluaciones que una corrida con `Portfolio` estándar bajo la misma semilla.

---

## 6. Riesgos y Salvaguardas

| Riesgo | Probabilidad | Impacto | Salvaguarda Metodológica |
| :--- | :---: | :---: | :--- |
| **Sobrecosto de Memoria en Corridas Largas** | Baja | Menor | Almacenar solo identificadores y metadatos en `SolutionProvenanceRecord`, sin duplicar schedules completos. |
| **Sobrecosto de CPU en Comparación de Conjuntos** | Baja | Menor | `ParetoArchive.entries` contiene entre 30 y 150 elementos; las diferencias de conjuntos tardan menos de 0.1 milisegundos por bloque. |
| **Confusión entre FE Descubrimiento e Incorporación** | Media | Moderada | Documentar explícitamente en todos los CSVs y visualizaciones que la métrica de tiempo registrada es `ingestion_fe`. |

---

## 7. Próximo Paso (Recomendación para P4)
Una vez aprobada esta propuesta, la implementación de P4 consistirá exclusivamente en:
1. Crear el módulo `src/mojssp/provenance.py` con las clases `SolutionProvenanceRecord`, `BlockProvenanceTrace` y el observador.
2. Desarrollar la suite de pruebas unitarias `tests/test_provenance_observability.py`.
3. Ejecutar un piloto determinista de 30 bloques sobre una única instancia de validación para certificar la bit-exactitud.

