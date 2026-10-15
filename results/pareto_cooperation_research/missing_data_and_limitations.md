# Datos Faltantes, Limitaciones Técnicas y Alcance Metodológico

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Fecha:** 2026-10-15  
**Entorno:** `mojssp-pareto-cooperation` (Commit `ea044c0`)

---

## 1. Inventario de Datos Faltantes y Archivos No Versionados

Siguiendo el principio de máxima honestidad científica y estricto respeto al aislamiento del repositorio original:

### 1.1. Archivo `src/mojssp/pairing.py` No Incluido en Commit `ea044c0`
- **Descripción:** El archivo `src/mojssp/__init__.py` (líneas 112-127) intenta importar símbolos desde `.pairing`. Sin embargo, `pairing.py` no fue añadido al árbol de Git en el commit de congelación `ea044c0`.
- **Análisis Afectados:** La importación de nivel superior `import mojssp` falla de forma nativa en un entorno limpio sin un stub en memoria de `mojssp.pairing`.
- **Mitigación Adoptada:** En esta auditoría se utilizó un stub en memoria sin alterar ningún archivo físico del repositorio, permitiendo la ejecución de análisis basados en los módulos centrales de optimización.

### 1.2. Directorio `data/generated/expanded_200/` No Versionado
- **Descripción:** Las instancias sintetizadas en formato `.dzn` dentro de `data/generated/expanded_200/` no forman parte del historial Git del commit `ea044c0`.
- **Análisis Afectados:** No es posible re-ejecutar nuevas corridas sobre estas instancias específicas desde este worktree sin los archivos `.dzn`.
- **Análisis Preservados:** Todos los resultados numéricos de las 450 corridas (vectores objetivo, hipervolúmenes, checkpoints, métricas de complementariedad y decisiones de bloque) están perfectamente preservados y versionados en `results/expanded_portfolio_phase2/`.

### 1.3. Directorio `results/expanded_complementarity_phase1/` No Versionado
- **Descripción:** Esta carpeta existía como archivo temporal/untracked en el entorno de desarrollo y no fue persistida en Git en `ea044c0`.
- **Análisis Afectados:** No se pueden auditar los experimentos exploratorios previos de la Fase 1 expandida desde este worktree.
- **Análisis Preservados:** La Fase 2 cuenta con su propio estudio de complementariedad exhaustivo (`complementarity_audit.csv` en `closure_audit/`), por lo que la auditoría de los 3 brazos definitivos no se vio comprometida.

---

## 2. Limitaciones de Trazabilidad en Datos Persistidos (Nivel 1 vs Nivel 2)

- **Ausencia de Genotipos en Disco:**
  - Los archivos `budget_fronts.jsonl` y `pilot_fronts.jsonl` almacenan exclusivamente las coordenadas 3D de los frentes de Pareto: $[C_{max}, T, E]$.
  - Los genotipos correspondientes (`Solution.sequence` y `Solution.modes`) no fueron exportados al formato JSONL durante las campañas de la Fase 2 para ahorrar espacio en disco.
  - **Consecuencia Metodológica:**
    - Es posible calcular métricas de espacio objetivo (Hypervolume, $\Delta HV$, $MC_i$, soluciones no dominadas exclusivas por vector).
    - **No es posible** inspeccionar directamente los genotipos de corridas históricas pasadas para estudiar solapamiento genotípico o similitud en secuencias de Bierwirth. Dicho análisis requerirá instrumentar el formato de guardado en futuras campañas.

---

## 3. Limitaciones Metodológicas y Estadísticas

### 3.1. Tratamiento de Perfiles Derivados de una Misma Base
- En el conjunto de 10 instancias, algunas comparten la misma matriz de operaciones base y únicamente varían en el perfil de fechas de entrega o consumo energético (por ejemplo, `base_c01_5x5_b03` y `base_c01_5x5_b05_tard_med`).
- **Advertencia Estadística:** No deben tratarse como observaciones estadísticas totalmente independientes. En esta auditoría se agregan y analizan a nivel de base independiente para no inflar artificialmente los grados de libertad ni reportar valores $p$ espurios.

### 3.2. Diferenciación entre Evidencia Exploratoria y Confirmatoria
- Los resultados de complementariedad de frentes obtenidos en el Escenario A (unión retrospectiva) son de carácter **exploratorio**: demuestran el potencial del espacio de soluciones combinado, pero no constituyen evidencia confirmatoria de que un portafolio interactivo activo vaya a capturar ese mismo frente bajo un presupuesto restringido.
- La confirmación requerirá ejecutar el diseño formal planteado en `proposed_cooperation_experiment.md` con réplicas pareadas y control estricto de semillas.

