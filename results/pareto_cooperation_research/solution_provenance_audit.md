# Auditoría de Trazabilidad y Procedencia de Soluciones

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Módulo Auditado:** Trazabilidad de Genotipos, Fenotipos y Procedencia Algorítmica  
**Fecha:** 2026-10-15  
**Entorno:** `mojssp-pareto-cooperation` (Commit `ea044c0`)

---

## 1. Niveles de Trazabilidad de Soluciones

Para evaluar la viabilidad técnica de una transferencia de soluciones (cooperación activa), es indispensable auditar qué información de cada individuo sobrevive en memoria y en disco.

Se definen tres niveles formales de trazabilidad:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Nivel 1: Vectores objetivos (Cmax, T, E)                               │
├────────────────────────────────────────────────────────────────────────┤
│ Nivel 2: Genotipo completo (secuencia Bierwirth + modos de velocidad)  │
│          + Fenotipo (Schedule temporal completo) + Objetivos           │
├────────────────────────────────────────────────────────────────────────┤
│ Nivel 3: Genotipo + Fenotipo + Objetivos + Algoritmo Productor         │
│          + Bloque de Descubrimiento + FE Acumuladas + Procedencia Múlt.│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Diagnóstico del Estado Actual del Repositorio

### 2.1. Trazabilidad en Memoria (Tiempo de Ejecución)
- **Estructura:** [`ArchiveEntry`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/pareto_archive.py#L14-L45)
  ```python
  @dataclass(frozen=True)
  class ArchiveEntry:
      solution: Solution      # Genotipo (sequence, modes)
      schedule: Schedule      # Fenotipo (inicio, fin, máquina por operación)
      objectives: ObjectiveValues  # (makespan, tardiness, energy)
  ```
- **Capacidad de Reconstrucción:**
  - El genotipo `Solution` está intacto. Contiene la tupla de operaciones de Bierwirth y el vector de modos discretos.
  - Se puede reconstruir el fenotipo idéntico llamando a `Decoder.decode(instance, solution)` o consultando directamente `entry.schedule`.
- **Información Ausente en Memoria:**
  - `ArchiveEntry` **no posee** atributos como `origin_arm`, `discovery_block`, `discovery_fe` o `producers: Set[str]`.
  - Cuando un brazo entrega sus soluciones a `Portfolio._global_archive`, se mezclan en una lista única de `ArchiveEntry`. Si un algoritmo posterior consulta el archivo global, no puede discernir qué solución fue producida por quién ni en qué bloque.
- **Nivel en Memoria:** **NIVEL 2 (Genotipo recuperable, pero procedencia y tiempo ausentes).**

### 2.2. Trazabilidad en Disco (Resultados Persistidos)
- **Estructura en Archivos JSON / JSONL:**
  - Inspección de [`results/expanded_portfolio_phase2/budget_diagnostic/budget_fronts.jsonl`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/results/expanded_portfolio_phase2/budget_diagnostic/budget_fronts.jsonl) y [`export_results_to_csv()`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/runner.py#L670-L686):
  ```json
  {
    "run_id": "base_c01_5x5_b03_MOEA_D_s42_b1000",
    "algorithm": "MOEA/D",
    "seed": 42,
    "budget": 1000,
    "hypervolume": 0.98342,
    "archive_size": 46,
    "pareto_front": [
      [252.0, 146.0, 1683.0],
      [261.0, 138.0, 1650.0]
    ]
  }
  ```
- **Evaluación:**
  - Los archivos `.jsonl` y `.json` almacenan únicamente los puntos 3D `[Cmax, T, E]`.
  - **No contienen** la tupla de Bierwirth ni la tupla de modos discretos de velocidad.
  - Por lo tanto, no es posible reconstruir los schedules de las soluciones a partir de los archivos de frentes históricos guardados en disco; solo se pueden analizar sus propiedades métricas en el espacio objetivo.
- **Nivel en Disco:** **NIVEL 1 (Solo vectores objetivos).**

---

## 3. Distinción entre Vectores Objetivo y Genotipos

Un principio metodológico clave para MO-JSSP con Speed Scaling es que:
$$f(x_1) = f(x_2) \not\implies x_1 = x_2$$

Dos soluciones pueden tener exactamente el mismo vector $(C_{max}, T, E)$ mediante:
1. Distintas permutaciones de operaciones que conducen a caminos críticos equivalentes.
2. Intercambio de modos de velocidad entre operaciones no críticas con igual compensación tiempo-energía.

### Comportamiento de la Arquitectura frente a Empates:
- En [`ParetoArchive.add_entry()`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/pareto_archive.py#L136-L144):
  - Comprueba `existing.solution == entry.solution`. Si el genotipo es el mismo, rechaza la inserción para evitar redundancia.
  - Pero si el vector objetivo coincide y el genotipo es diferente, **ambas soluciones son preservadas**.
- Sin embargo, como el archivo no registra la procedencia múltiple, si el algoritmo A encuentra una solución con vector $v$ y luego el algoritmo B encuentra otra solución distinta con idéntico vector $v$, ambas están en el archivo, pero no hay forma de saber retrospectivamente cuál fue generada por B sin auditar el histórico de bloques.

---

## 4. Requisitos de Instrumentación para Cooperación Activa

Para que la cooperación activa sea científicamente defendible y trazable, el sistema requiere alcanzar **Nivel 3**:
1. Extender `ArchiveEntry` (o crear una clase enriquecida `TaggedArchiveEntry`) con:
   - `origin_arm: str` (brazo que evaluó la solución por primera vez).
   - `discovery_block: int` (índice del bloque).
   - `discovery_fe: int` (evaluaciones acumuladas globales al momento de su evaluación).
   - `producers: Set[str]` (conjunto de brazos que redescubrieron independientemente el mismo genotipo o vector).
2. Opcionalmente, si se desea persistir frentes completos con genotipos, habilitar un formato serializado de `Solution` (`sequence` como lista de enteros, `modes` como lista de enteros) en un directorio `schedules/` o `solutions/`.

