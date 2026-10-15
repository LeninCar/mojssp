# Conservación del trabajo MO-JSSP

Fecha de preparación: 2026-10-15T21:32:37.025779+00:00.

Rama conservada: `experiment/pareto-archive-cooperation`. Sin push, cambio de rama, cambios de algoritmos ni nuevas optimizaciones durante esta conservación.

## Respaldo independiente

Ubicación fuera del repositorio: `C:\Users\lenin\Documents\Ingeniería\2026-1\TG1\mojssp-preservation-20261016-20261015T212824499174Z\verified_snapshot`.

`checkout_before_commits/` conserva todos los archivos anteriores a los commits, incluidos ignorados y `.git` completo con objetos huérfanos, reflogs y referencias. `checkout_manifest.json` registra SHA256 y tamaño de cada archivo. `historical_dependencies/manifest.json` identifica procedencia y ubicación de las dependencias históricas: una parte se reutiliza desde la copia independiente del checkout y el resto está en `historical_dependencies/payload/`. Mantener siempre el directorio completo; no trasladar el payload aislado.

Hash SHA256 del manifiesto del checkout: `53433c21772a73b3590a0939d7d98a14df2e28b37d30703674b98df5b0dba8ad`.

Hash SHA256 del manifiesto histórico: `9a8041063b6a0d02b9a63e70d34f7c08946e615ab2bd90d45e5c78dd3c19573e`.

El primer intento, en el directorio padre del respaldo verificado, quedó incompleto por el límite de rutas de Windows. Se conserva sin sobrescribir y no debe usarse para recuperar. El respaldo verificado usa rutas largas.

## Recuperación segura

Ejecutar desde PowerShell con Python 3.12, sustituyendo la ruta de recuperación por un directorio nuevo y vacío que NO exista. Ningún comando de recuperación debe apuntar a los repositorios originales.

```powershell
$b = 'C:\Users\lenin\Documents\Ingeniería\2026-1\TG1\mojssp-preservation-20261016-20261015T212824499174Z\verified_snapshot'
python "$b/recover.py" verify
# Estado completo anterior a los commits, incluidos Git y objetos huérfanos:
python "$b/recover.py" restore-checkout --destination 'C:/MOJSSP_RECOVERY_PRE/mojssp-loop-agent'
# Dependencias históricas, reconstruidas con sus rutas relativas originales:
python "$b/recover.py" restore-historical --destination 'C:/MOJSSP_RECOVERY_PRE/mojssp-dmab'
```

Después de los commits se genera además `committed_history.bundle` y un informe final fuera del repositorio. Para recuperar directamente ambos commits en otro destino nuevo:

```powershell
git -c core.autocrlf=false clone --config core.autocrlf=false --branch experiment/pareto-archive-cooperation "$b/committed_history.bundle" 'C:/MOJSSP_RECOVERY_COMMITTED/mojssp-loop-agent'
python "$b/recover.py" restore-historical --destination 'C:/MOJSSP_RECOVERY_COMMITTED/mojssp-dmab'
```

El bundle conserva historia referenciada y commits; la copia completa anterior conserva además objetos huérfanos y archivos ignorados. Los entornos `.venv` copiados no se consideran portables: las versiones de ejecución están registradas en `results/portfolio_loop_20261015/requirements-experiment.txt`, `results/reunion_directores_20261016/evidence/analysis_runtime_versions.json` y `evidence/analysis_audit.json`. No instalar ni ejecutar optimizaciones automáticamente.

Los scripts históricos contienen algunas rutas absolutas. Al trasladar a otra máquina, adaptar una COPIA de esos scripts/configuraciones a la raíz nueva, conservando intactos los originales y sus hashes. La reproducción de un corte histórico no exige abrir datos reservados ni refrescar campañas externas posteriores.

## Alcance y exclusiones

Primer commit: mecanismos ya implementados, ocho runners/análisis, prueba de cooperación y una instancia necesaria (14 archivos). Segundo: campaña del 15 de octubre, informes de reunión, diseño P5 y estos metadatos de conservación. Los dos manifiestos históricos originales permanecen intactos.

Las dependencias históricas voluminosas se conservan fuera de Git con manifiesto; no se incorporan automáticamente a los commits. Cachés, `.venv` y temporales ignorados no se versionan. El objeto temporal preexistente de Git se preserva en el respaldo completo sin limpieza.

El remoto de este checkout apunta a otro repositorio local, no a un respaldo externo. No se hizo push. El respaldo es independiente del checkout, pero reside en el mismo disco; para tolerar pérdida del equipo se necesita copiar el directorio completo a otro medio y verificarlo allí con `recover.py verify`.
