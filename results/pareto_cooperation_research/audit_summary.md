# Resumen Ejecutivo y Dictámenes Finales de la Auditoría

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Autor:** Antigravity (Auditoría Técnica Independiente)  
**Fecha:** 2026-10-15  
**Entorno de Trabajo:** Worktree Aislado `mojssp-pareto-cooperation` (Commit `ea044c0`)

---

## 1. Síntesis de Aspectos Verificados

1. **Aislamiento de Entornos:**
   - Se verificó que el repositorio principal `mojssp-dmab` permanece intacto en la rama `experiment/page-hinkley-dmab`, sin modificaciones locales sobreescritas y sin alteración en sus archivos de Page-Hinkley.
   - El worktree `mojssp-pareto-cooperation` se creó exitosamente desde el commit estable `ea044c0` (`v0.2.0-phase2-closure`).
2. **Arquitectura del Archivo Pareto Global:**
   - Se verificó la implementación de `ParetoArchive`, `Portfolio` y los brazos `NSGA2Arm`, `MOEADArm` y `SPEA2Arm`.
   - Se comprobó que el archivo global es acumulativo, no acotado y se actualiza después de cada bloque.
   - Se comprobó que ninguna solución no dominada descubierta por un brazo se pierde antes de llegar al archivo global.
   - Se comprobó que el archivo preserva duplicados objetivos cuando el genotipo es diferente.
3. **Cálculo de Hypervolume:**
   - Se verificó que el Hypervolume para recompensas del DMAB, checkpoints y resultado final se calcula de manera unificada y coherente sobre el archivo global, utilizando cotas min-max de la instancia y el punto de referencia canónico $(1.1, 1.1, 1.1)$.
   - Se verificó la monotonía estricta del HV acumulado en los 15.000 checkpoints históricos (cero violaciones).
4. **Complementariedad Cuantitativa:**
   - Se auditaron 450 corridas y se analizaron los 90 frentes retrospectivos (10 instancias $\times$ 3 semillas $\times$ 3 presupuestos), calculando $\Delta HV$, contribuciones marginales $MC_i$ y exclusividad de soluciones.

---

## 2. Aspectos que No Pudieron Verificarse

1. **Inspección Genotípica Retrospectiva:**
   - Los archivos de frentes en disco (`.jsonl`) contienen únicamente los vectores objetivos $(C_{max}, T, E)$ y no las cadenas de Bierwirth ni modos. Por ende, la diversidad genotípica de las corridas históricas pasadas no puede reconstruirse directamente desde el disco.
2. **Re-ejecución Directa de Instancias de la Suite Ampliada:**
   - La carpeta `data/generated/expanded_200/` no estaba incluida en el historial de Git en `ea044c0`, lo que impide ejecutar nuevas corridas sobre esas instancias específicas desde este worktree limpio sin copiar previamente los `.dzn`.

---

## 3. Problemas Reales Identificados en el Código Base

1. **Dependencia Huérfana en `src/mojssp/__init__.py`:**
   - En el commit `ea044c0`, `__init__.py` importa `mojssp.pairing`, pero `src/mojssp/pairing.py` no fue commiteado en Git. En un entorno limpio, `import mojssp` falla sin un stub en memoria.
2. **Carencia de Metadatos de Procedencia en Memoria (Nivel 3 Ausente):**
   - La clase `ArchiveEntry` almacena `solution`, `schedule` y `objectives`, pero carece de `origin_arm`, `discovery_block` y `discovery_fe`. Al unirse en el archivo global, se pierde la información de qué brazo generó cada solución.
3. **Incompatibilidad Estructural para Inyección Directa en MOEA/D:**
   - MOEA/D organiza sus soluciones rígidamente en subproblemas de descomposición con vectores de peso fijos. No se puede inyectar una solución arbitraria sin calcular la función de agregación Tchebycheff y asociarla al subproblema afín.

---

## 4. Métricas Clave Calculadas (Resumen Empírico)

- **Frente Unión ($|U|$ a 5.000 FE):** $88.63$ soluciones no dominadas promedio.
- **Distribución de Soluciones Exclusivas en $U$ (a 5.000 FE):**
  - **MOEA/D:** $41.90$ soluciones exclusivas ($47.3\%$)
  - **SPEA2:** $28.50$ soluciones exclusivas ($32.1\%$)
  - **NSGA-II:** $18.23$ soluciones exclusivas ($20.6\%$)
  - **Soluciones compartidas por $\ge 2$ algoritmos:** $0.00$ ($0.0\%$)
- **Ganancia Retrospectiva $\Delta HV$ (a 5.000 FE):** $+0.00955$ ($+0.92\%$ relativo respecto al mejor standalone).
- **Contribuciones Marginales al Hypervolume ($MC$ a 5.000 FE):**
  - $MC_{\text{MOEA/D}} = 0.08832$
  - $MC_{\text{SPEA2}} = 0.01023$
  - $MC_{\text{NSGA-II}} = 0.00534$
- **Brecha Escenario A vs Escenario B (a 5.000 FE):** $+0.06785$ (El portafolio pasivo compartido rinde menos que la unión retrospectiva debido al aislamiento poblacional y la división del presupuesto).

---

## 5. Los Dos Dictámenes Finales Obligatorios

### Dictamen Técnico del Archivo Global:
> ### **A — CORRECTO**
> **Justificación:** La implementación de `ParetoArchive`, `Portfolio` y `HypervolumeRewardTracker` conserva de manera impecable el frente no dominado de todas las soluciones efectivamente evaluadas y recibidas de los tres brazos. No existe pérdida de soluciones no dominadas, se manejan adecuadamente los empates objetivos preservando genotipos distintos, y el Hypervolume final reportado por el runner corresponde estrictamente al estado final del archivo global acumulado, exhibiendo una monotonía rigurosamente verificada.

---

### Dictamen Científico sobre Cooperación Activa:
> ### **B — PROMETEDORA, PERO REQUIERE INSTRUMENTACIÓN**
> **Justificación:** Existe evidencia empírica contundente de complementariedad espacial entre MOEA/D, NSGA-II y SPEA2 en la unión retrospectiva (Escenario A), y la brecha negativa del portafolio actual frente al mejor standalone (Escenario B) proporciona una justificación científica sólida para explorar la transferencia de soluciones. Sin embargo, no se recomienda implementar cooperación activa de forma inmediata porque:
> 1. El archivo no dispone de trazabilidad de procedencia en memoria (Nivel 3).
> 2. No existe un operador formal de mapeo escalar Tchebycheff para incorporar soluciones externas en los subproblemas de MOEA/D sin distorsionar sus invariantes de descomposición.
> 3. Se requiere un protocolo previo de salvaguarda de diversidad en NSGA-II y SPEA2 para evitar el colapso genético prematuro.

---

## 6. Recomendación Única para el Siguiente Paso

> **Recomendación:** Incorporar primero los campos de trazabilidad de procedencia (`origin_arm`, `discovery_block`, `discovery_fe`) en `ArchiveEntry` y desarrollar de manera aislada una función pura de mapeo de soluciones a subproblemas de MOEA/D con pruebas unitarias deterministas, **antes** de habilitar cualquier transferencia entre algoritmos o ejecutar el experimento propuesto.

