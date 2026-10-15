# Preservación, trazabilidad y corte de evidencia

Se inició en el checkout experimental `mojssp-loop-agent`, rama `experiment/pareto-archive-cooperation`, HEAD `1d695f3efa45d261da89bd7ba832730c33c9d4ca`. Git registra sólo este worktree: el checkout es una copia independiente. No se cambió de rama ni se hizo push.

Antes del análisis se registraron 5236 archivos de fuente, scripts, tests, datos y resultados en cuatro checkouts. El estado Git ya contenía cambios de la campaña reciente: tres brazos modificados, cooperación, scripts y resultados sin seguimiento. Se conserva el [diff inicial](evidence/preexisting_algorithm_changes.diff). Los scripts de esta auditoría sólo escriben en el directorio de reunión.

| Checkout | Rama / HEAD inicial | Conservación observada |
|---|---|---|
| mojssp-loop-agent | experiment/pareto-archive-cooperation / 1d695f3 | Fuente y resultados previos sin cambios; sólo nuevos productos de reunión |
| mojssp-dmab | experiment/page-hinkley-dmab / 47af7eb | Consulta en lectura; estado inicial conservado |
| mojssp-dmab - copia | experiment/page-hinkley-dmab / 47af7eb | Desapareció externamente durante la tarea; no se restauró |
| mojssp-pareto-cooperation | experiment/pareto-archive-cooperation / 1d695f3 | Otro proceso produjo P7 y actualizó su diseño; corte adicional separado |

La [preservación inicial](evidence/preservation_before.json) no se sobrescribe. La [verificación final](evidence/verification.json) distingue integridad del checkout autorizado, del repositorio original y cambios externos observados. No se certifica inmutabilidad global de directorios externos. El recuento de 1336 contenidos/2746 copias corresponde al inicio; algunas rutas de copias desaparecidas ya no existen, aunque sus hashes permanecen registrados.


| campaign | date | code_version | FE | n_instances | n_base_clusters | n_seeds | n_records |
| --- | --- | --- | --- | --- | --- | --- | --- |
| phase1_40_profiles | 2026-10-14 17:38:56 | not_recorded | 1000 | 40 | 8 | 5 | 600 |
| technical_benchmark | 2026-10-14 16:40:01 | not_recorded | 1000 | 8 | 8 | 1 | 40 |
| phase2_pilot | 2026-10-14 19:09:43 | a5566d477b352d20d39b40e3cf9c05d6fd6bb24b | 1000 | 10 | 10 | 3 | 150 |
| phase2_budget | 2026-10-14 19:45:10 | a5566d477b352d20d39b40e3cf9c05d6fd6bb24b | 1000;3000;5000 | 10 | 10 | 3 | 450 |
| page_hinkley_final | metadata/file_times_only | not_recorded | 5000 | 10 | 10 | 3 | 90 |
| legacy_raw | metadata/file_times_only | not_recorded | 500;1000 | 12 | 12 | 3 | 180 |
| legacy_pilot | metadata/file_times_only | not_recorded | 1000 | 5 | 5 | 5 | 125 |
| legacy_f86 | metadata/file_times_only | not_recorded | 1000 | 5 | 5 | 10 | 200 |
| legacy_f865 | metadata/file_times_only | not_recorded | 1000 | 37 | 37 | 10 | 1480 |
| legacy_f86_uniform | metadata/file_times_only | not_recorded | 1000 | 5 | 5 | 10 | 50 |
| legacy_c_calibration | metadata/file_times_only | not_recorded | 1000 | 3 | 3 | 5 | 105 |
| loop_development | 2026-10-15 | 1d695f3 + frozen source snapshots; baseline provenance correction | 3000 | 6 | 6 | 3 | 144 |
| loop_confirmation | 2026-10-15 | 1d695f3 + frozen source snapshots; baseline provenance correction | 3000 | 8 | 8 | 3 | 168 |
| page_hinkley_calibration | October 2026; exact runtime date not recorded | experiment/page-hinkley-dmab; loaded source snapshot absent | 5000 | 10 | 10 | 3 | 270 |
| p5_c_sensitivity | 2026-10-15T20:55:37.499964+00:00 | Sibling checkout 1d695f3 + P6 working tree; snapshot of current source, loaded-state not certified | 1000 | 2 | 2 | 1 | 8 |
| p6_injection_pilot | 2026-10-15T20:55:37.499964+00:00 | Sibling checkout 1d695f3 + P6 working tree; snapshot of current source, loaded-state not certified | 1000 | 2 | 2 | 1 | 8 |
| p6_fixed_control | 2026-10-15T20:55:37.499964+00:00 | Sibling checkout 1d695f3 + P6 working tree; snapshot of current source, loaded-state not certified | 1000 | 2 | 2 | 1 | 2 |
| p7_partial_external | 2026-10-15T20:55:37.499964+00:00 | Sibling checkout 1d695f3 + P6 working tree; snapshot of current source, loaded-state not certified | 1000 | 10 | 10 | 5 | 317 |


El [inventario completo](tables/campaign_inventory.csv) contiene métodos, FE, semillas, configuración, métricas, rutas y limitaciones. Los 450 cortes históricos son 150 trayectorias; las 30 filas PH C5 se reutilizan de calibración. Las fuentes recientes están congeladas en cuatro árboles y un índice SHA-256, con una corrección explícita del código cargado de la base. Un commit histórico no garantiza capturar cambios sucios usados al ejecutar.

Las instancias reservadas sólo se inventarían con metadatos/hashes. No se analizó rendimiento de holdout. P7 tiene una instantánea fija a 2026-10-15T20:55:37.499964+00:00, sin iniciar ni esperar nuevas optimizaciones. Sus resultados provisionales no sustituyen la confirmación reciente de 3000 FE.
