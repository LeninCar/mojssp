# Informe de Aislamiento de Worktree e Inventario Inicial

**Fecha:** 2026-10-15  
**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Autor:** Antigravity (Auditoría Técnica Independiente)  
**Entorno de Trabajo:** Worktree Aislado `mojssp-pareto-cooperation`

---

## 1. Verificación del Repositorio Original y Aislamiento

Antes de cualquier operación, se inspeccionó exhaustivamente el repositorio original ubicado en:
`C:\Users\lenin\Documents\Ingeniería\2026-1\TG1\mojssp-dmab`

### 1.1. Diagnóstico del Árbol Original
- **Rama activa:** `experiment/page-hinkley-dmab`
- **Commit HEAD:** `ea044c02d0380812d3146d301791a739cdbe025a` (`ea044c0`)
- **Archivos modificados con seguimiento:**
  - `src/mojssp/__init__.py`
  - `src/mojssp/dmab.py`
  - `src/mojssp/orchestrator.py`
  - `src/mojssp/runner.py`
- **Archivos y carpetas sin seguimiento (en uso por el agente de Page-Hinkley):**
  - Scripts de calibración y comparación de Page-Hinkley (`scripts/run_f3_ph_*.py`, etc.)
  - Pruebas unitarias de Page-Hinkley (`tests/test_page_hinkley_*.py`, `tests/test_change_detection.py`, etc.)
  - Resultados en curso en `results/page_hinkley_research/`, `results/expanded_benchmark/`, etc.
  - Instancias y emparejamientos en `data/generated/expanded_200/`, `data/generated/paired/`.

### 1.2. Medidas de No-Interferencia Aplicadas
- No se ejecutó `git stash`, `git reset`, `git clean` ni `git checkout` en el directorio de trabajo original.
- No se modificó ningún archivo del directorio original.
- No se realizaron commits ni push en ninguna rama.

---

## 2. Creación y Configuración del Worktree Aislado

Se procedió a crear un worktree independiente en el directorio hermano:
`C:\Users\lenin\Documents\Ingeniería\2026-1\TG1\mojssp-pareto-cooperation`

### 2.1. Comando Ejecutado
```powershell
git worktree add -b experiment/pareto-archive-cooperation ..\mojssp-pareto-cooperation ea044c0
```

### 2.2. Verificación de Invariantes del Worktree
| Criterio | Valor Esperado | Valor Observado | Estado |
| :--- | :--- | :--- | :--- |
| **Directorio de trabajo** | `..\mojssp-pareto-cooperation` | `C:\Users\lenin\Documents\Ingeniería\2026-1\TG1\mojssp-pareto-cooperation` | **PASS** |
| **Rama asignada** | `experiment/pareto-archive-cooperation` | `experiment/pareto-archive-cooperation` | **PASS** |
| **Commit HEAD** | `ea044c0` | `ea044c02d0380812d3146d301791a739cdbe025a` | **PASS** |
| **Estado de trabajo** | Limpio (sin modificaciones locales) | `nothing to commit, working tree clean` | **PASS** |
| **Estado del repositorio original** | Preserva rama `experiment/page-hinkley-dmab` y archivos locales | Intacto, sin cambios en archivos modificados ni untracked | **PASS** |

Ambos worktrees comparten la base de objetos de Git (`.git/`), pero sus árboles de trabajo e índices están estrictamente desacoplados en el sistema de archivos.

---

## 3. Limitaciones Iniciales de Reproducibilidad Detectadas en `ea044c0`

Durante la inspección del checkout limpio en `mojssp-pareto-cooperation`, se detectaron dos hallazgos estructurales relevantes en el commit histórico `ea044c0`:

1. **Importación huérfana en `src/mojssp/__init__.py`:**
   - Línea 112: `from .pairing import (...)`.
   - El archivo `src/mojssp/pairing.py` existía únicamente como archivo sin seguimiento en el entorno de desarrollo y **no fue incluido en el commit `ea044c0`**.
   - Consecuencia: Cualquier llamada directa a `import mojssp` falla en un entorno limpio sin un stub en memoria de `mojssp.pairing`.
   - Solución metodológica adoptada en esta auditoría: Se inyecta un stub en memoria de `mojssp.pairing` en scripts de análisis sin modificar ningún archivo en el disco, preservando la inmutabilidad exigida.

2. **Conjuntos de datos no versionados:**
   - La carpeta `data/generated/expanded_200/` y `results/expanded_complementarity_phase1/` no están en el historial de Git (fueron ignoradas o no commiteadas).
   - Sin embargo, **todos los resultados experimentales finales de la Fase 2 (Phase 2 closure)** están plenamente versionados en `results/expanded_portfolio_phase2/` (`budget_diagnostic/`, `pilot/`, `closure_audit/` y `final_closure/`), conteniendo las 450 corridas, sus 15.000 checkpoints, frentes de Pareto completos y auditorías de complementariedad.
   - De acuerdo con la regla del usuario, **no se copiaron archivos desde el repositorio original**.

