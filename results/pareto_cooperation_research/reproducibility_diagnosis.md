# Diagnóstico de Reproducibilidad del Entorno y Dependencias (P3.5-B)

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Autor:** Antigravity (Auditoría Técnica Independiente)  
**Fecha:** 2026-10-15  
**Entorno de Trabajo:** Worktree Aislado `mojssp-pareto-cooperation` (Rama `experiment/pareto-archive-cooperation`, Commit `ea044c0`)

---

## 1. Causa Raíz de la Ausencia de `mojssp.pairing`

Al rastrear el historial de Git entre los commits `7d97f02` y `473908a`:

1. **Commit de Introducción:** En el commit `473908ab88` (*"feat(portfolio): integrate 3-arm portfolio with SW-UCB and Round-Robin selectors"*), se modificó [`src/mojssp/__init__.py`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/__init__.py#L112-L141) para exportar las utilidades de emparejamiento de instancias:
   ```python
   from .pairing import (
       CheckResult, RawDznData, ReferenceSample, ValidationReport,
       derive_btnk_high, derive_nrg_strong, derive_tard_high, derive_tard_med,
       derive_tardiness_variant, format_validation_report,
       generate_reference_sample, read_dzn_raw, validate_pairing, write_dzn_raw,
   )
   ```
2. **Ovisión de Git Staging:** El archivo `src/mojssp/pairing.py` fue creado en el entorno de trabajo del autor, pero **nunca se incluyó en el `git add`** de ese commit ni en los posteriores (`335b98e`, `ea044c0`).
3. **Estado Actual en el Repositorio Original:** En `mojssp-dmab`, el archivo permanece como archivo sin seguimiento (`?? src/mojssp/pairing.py`). En el árbol versionado de Git no existe.

---

## 2. Mapa de Dependencias del Código

Se ejecutó un análisis de dependencias cruzadas sobre la totalidad del código versionado en `ea044c0`:

| Componente | Total Archivos | Archivos que Importan o Usan `mojssp.pairing` | Impacto Real |
| :--- | :---: | :---: | :--- |
| **Núcleo Algorítmico (`src/mojssp/`)** | 24 | **1** (`src/mojssp/__init__.py`) | Cero dependencias en algoritmos, decodificador, evaluador, orquestador o archivo global. |
| **Suites de Pruebas (`tests/`)** | 42 | **0** | Ninguna prueba unitaria o de integración de Fase 2 hace referencia a `pairing`. |
| **Scripts Ejecutables (`scripts/`)** | 36 | **0** | Ningún script de runner, análisis o auditoría de Fase 2 utiliza `pairing`. |

**Conclusión:** `mojssp.pairing` es un módulo auxiliar para la síntesis de instancias pareadas y **no forma parte del pipeline de ejecución, optimización ni evaluación del portafolio**.

---

## 3. Propuesta de Corrección Mínima Segura

### 3.1. Por qué un `except ImportError: pass` Genérico es Peligroso
Un bloque `try ... except ImportError: pass` genérico presenta un riesgo metodológico grave:  
Si `pairing.py` se añade posteriormente al repositorio pero contiene un error de importación interno (por ejemplo, una dependencia faltante, un error de sintaxis en `import re` o una función mal renombrada), la excepción `ImportError` sería silenciada inadvertidamente, ocultando un fallo real del sistema y haciendo creer que el archivo simplemente no existe.

### 3.2. Opciones de Corrección Segura (Pendientes de Autorización)

- **Opción Recomendada 1 (Captura Específica por Nombre de Módulo):**
  Modificar [`src/mojssp/__init__.py`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/src/mojssp/__init__.py#L112) restringiendo la excepción estrictamente a la ausencia del módulo raíz `pairing`:
  ```python
  try:
      from .pairing import (
          CheckResult, RawDznData, ReferenceSample, ValidationReport,
          derive_btnk_high, derive_nrg_strong, derive_tard_high, derive_tard_med,
          derive_tardiness_variant, format_validation_report,
          generate_reference_sample, read_dzn_raw, validate_pairing, write_dzn_raw,
      )
  except ModuleNotFoundError as _err:
      # Permitir la ausencia únicamente si el archivo faltante es el propio 'pairing'
      if _err.name not in ("mojssp.pairing", "pairing"):
          raise
  ```
  *Ventaja:* Si `pairing.py` existe pero contiene un error interno, el sistema lanza la excepción y no la oculta.

- **Opción Recomendada 2 (Poda Limpia del `__init__.py`):**
  Eliminar las líneas 112–127 y los símbolos respectivos en `__all__` de `src/mojssp/__init__.py`. Como ningún módulo depende de ellos, el paquete queda 100% autocontenido y funcional sin stubs.

- **Opción 3 (Completitud por Archivo):**
  Solicitar autorización para importar `src/mojssp/pairing.py` (existente en el workspace original como archivo sin seguimiento) hacia este worktree.

---

## 4. Diagnóstico de Datos de Desarrollo Faltantes

### 4.1. Conjuntos Ausentes en este Worktree
1. **Instancias de la Suite Ampliada (`data/generated/expanded_200/`):**
   - Las 10 instancias del diagnóstico de presupuesto (`base_c01_5x5_b03.dzn` a `base_c08_50x50_b03_btnk_high.dzn`) pertenecen al split de desarrollo (`development`), según consta en `budget_manifest.csv`.
   - No están versionadas en Git (estaban sin seguimiento en el workspace original).
2. **Suite de Validación Existente en este Worktree:**
   - En `data/validation/` sí existen 3 instancias versionadas: `small_3x2.dzn`, `small_3x3.dzn` y `toy_instance.dzn`.
   - En `data/experimental/` existen 12 instancias del benchmark estándar: `5_10_2-5_1.dzn` a `50_50_2-5_1.dzn`.

### 4.2. Estrategia para Obtener los Datos sin Modificar el Repositorio Original
- Las 10 instancias de desarrollo pueden leerse directamente de forma **estrictamente de solo lectura** desde `..\mojssp-dmab\data\generated\expanded_200\` sin necesidad de duplicarlas ni copiarlas en este worktree.
- En caso de requerir que el worktree sea autónomo sin depender de rutas relativas al workspace vecino, el usuario podrá autorizar una copia explícita de solo esas 10 instancias de desarrollo.
- **Garantía:** No se accederá en ningún caso a instancias del split `holdout`.

