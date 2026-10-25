# Reproducción de análisis existente, sin FE nuevas

Desde la raíz del repositorio, con Python3.12.8, numpy2.5.3, pandas2.2.3, scipy1.16.2 y matplotlib3.10.1:

```powershell
python -B -X utf8 results/seleccion_temprana_20261016/scripts/analyze_v3.py --run-id replica_usuario
```

El namespace debe ser nuevo. `analyze_v3.py` sólo lee registros existentes y crea tablas/evidencia. No importa ni instancia algoritmos/evaluator; `-B` evita cachés de código. Para los suplementos en ese namespace, adaptar una COPIA de `supplement_v2.py` cambiando únicamente T a `tables/replica_usuario`.

La reproducción automática de control está en `scripts/reproduce_check.py`: crea `tables/replica/`, ejecuta el análisis y suplemento en namespace nuevo y compara bytes. Ya ejecutada, no se puede volver a usar con el mismo destino; consultar su certificado en `evidence/reproduction_result.json`. Los tiempos de este análisis no son tiempos de optimización.

Puntos de entrada operativos: analyze_v3.py, supplement_v2.py, plot.py y report.py. `analyze.py` y `supplement.py` fueron borradores con errores de sintaxis conservados; analyze_v2.py produjo tablas intermedias v1. Las salidas autoritativas son v2. El cambio v1→v2 corrigió la contabilidad de coste cero del baseline E; no cambió sus aciertos ni se alteró ningún dato original.

Las fuentes externas se leen de los snapshots de la auditoría anterior. No se consulta el repositorio original vivo, no se cargan instancias reservadas y no se ejecutan los runners experimentales. El manifiesto nuevo registra hashes de fuentes y productos; la auditoría anterior se verifica byte por byte antes de cerrar.
