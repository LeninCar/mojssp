# Reunión MO-JSSP · 16 de octubre de 2026

Empezar por [resumen ejecutivo](26_resumen_ejecutivo.md), [guion de 13 minutos](27_guion_reunion.md) y [cinco decisiones](29_decisiones_directores.md). El [informe integral](INFORME_INTEGRAL_MOJSSP.md) consolida la discusión técnica. Las conclusiones diferencian hechos, interpretaciones e hipótesis.

## Hallazgos principales

1. UCB escalado mejora SW-UCB original en HV final y AUC en las ocho bases de confirmación interna a 3000 FE; ΔHV +0.020680, Holm .015625.
2. El portafolio escalado aún tiene menor HV medio que MOEA/D: .931368 frente a .951055, y pierde en siete de ocho bases.
3. SPEA2 gana la base 5×5 de confirmación; NSGA-II también supera allí a MOEA/D. No existe superioridad individual uniforme.
4. Padre externo con replay mejora HV medio +.008539 y diversidad genética +11.84%, pero HV corregido p=.054688 y requiere una asignación externa.
5. La combinación escalado + guía no añadió una mejora reproducible: ΔHV −.001742 frente a escalado en desarrollo; no se confirmó.
6. La complementariedad geométrica es positiva y asimétrica; a 5000 FE/brazo MOEA/D aporta MC .030796 frente a .003065/.003849. La unión cuesta 15000 FE.
7. Page-Hinkley C5 gasta 165 FE medias en resondeo y no acredita ventaja corregida frente a SW-UCB. Su comparación reutiliza los resultados de calibración C5.
8. El inventario contiene 1336 instancias por contenido y 2746 copias; sólo una pequeña parte tiene comparaciones actuales. Holdout: 80 variantes de 16 bases, sin abrir para rendimiento.
9. No puede afirmarse una regla general algoritmo–tamaño. La confirmación tiene 4 bases pequeñas, 1 mediana y 3 grandes; tamaño y perfil están confundidos.
10. El ensayo histórico de cuello de botella favorece la ventaja relativa de NSGA-II en 8/8 bases, pero tras ocho contrastes Holm queda en .0625: es una hipótesis dirigida para confirmar.

## Diez gráficas para explicar el proyecto

- [Comparación principal de calidad final](figures/01_hv_confirmacion.png)
- [Ganancia respecto a SW-UCB original](figures/02_diferencias_pareadas.png)
- [Calidad durante la búsqueda](figures/03_hv_fe.png)
- [Cómo cambia el reparto de FE](figures/05_asignacion.png)
- [Contribución marginal bajo asignación adaptativa](figures/06_contribuciones.png)
- [Regiones exploradas por algoritmos individuales](figures/07_frentes_proyecciones.png)
- [Rendimiento individual frente al tamaño](figures/09_hv_tamano.png)
- [Diversidad y calidad responden de forma distinta](figures/10_cooperacion_diversidad.png)
- [Escala de explotación y exploración](figures/11_escala_ucb.png)
- [Page-Hinkley no acredita una ventaja](figures/12_page_hinkley.png)

## Versiones del portafolio

| Versión | Selección / asignación | Información compartida | Evidencia | Estado |
| --- | --- | --- | --- | --- |
| Histórico NSGA-II/MOPSO/NSGA-II+LS | SW-UCB y uniforme; brazos anteriores | Unión pasiva; búsqueda local sólo dentro de su brazo | 500/1000 FE; campañas F8 | Antecedente; no mezclar con los tres brazos actuales |
| MOEA/D, NSGA-II, SPEA2 individuales | Un brazo usa todo B | Sin intercambio | 1000, 3000, 5000; reciente 3000 | Controles vigentes |
| Uniforme RR | Bloques cíclicos de 50 FE | Archivo global como salida | Fase 2 y reciente | Control de fragmentación y agregación |
| SW-UCB original | Media ΔHV + bono; W=10,c=.07 | Archivo global mide recompensa; sin padre externo | Fase 2, PH y reciente | Línea base conservada |
| UCB1 acumulativo | Media de todas las recompensas + bono | Sin transferencia genética | PH: 5000 FE, 10 bases × 3 semillas | Control de olvido |
| UCB1 + Page-Hinkley C5 | Alarma reinicia crédito; δ=.0005, λ=.020 | Poblaciones y archivo se conservan | 270 calibración + 90 comparación, 5000 FE | No adoptado; sin ventaja corregida |
| UCB escalado | Media ΔHV / máximo reciente + mismo bono | Sin cooperación genética | 6 desarrollo y 8 confirmación, 3000 FE | Mejora reproducible frente a SW-UCB |
| Padre externo con replay | Copia exactamente la asignación del control SW-UCB | Un padre extranjero cada 10 cruces elegibles | 6 desarrollo y 8 confirmación, 3000 FE tratamiento | Evidencia condicional; coste del control adicional |
| Escalado + padre externo | Decisiones online con crédito escalado | Mismo mecanismo de padre externo | Sólo 6 desarrollo × 3 semillas, 3000 FE | No adoptado; sin ganancia adicional clara |
| SW-UCB c=.01/.03 (P5 paralelo) | Reducir el bono sin escalar crédito | Unión pasiva | 2 bases × una semilla; 1000 FE | Sensibilidad exploratoria; ver apéndice 32 |
| Inyección acotada P6/P7 paralela | SW-UCB c=.01 y secuencia fija | Hasta 2 incumbentes evaluados por bloque desde índice 6 | P6: 2 bases × una semilla; P7 parcial 1000 FE | Distinta de padre externo; corte externo separado |


## Algoritmos por tamaño (confirmación, 3000 FE)

| size | n_base_clusters | MOEA/D | NSGA-II | SPEA2 | Mayor media |
| --- | --- | --- | --- | --- | --- |
| grande | 3 | 0.909396 | 0.889883 | 0.890158 | MOEA/D |
| mediana | 1 | 0.907217 | 0.884035 | 0.875291 | MOEA/D |
| pequena | 4 | 0.993259 | 0.984074 | 0.976691 | MOEA/D |


## Entregables por fase

- [01_evolucion_investigacion.md](01_evolucion_investigacion.md)
- [02_arquitectura_portafolio.md](02_arquitectura_portafolio.md)
- [03_catalogo_algoritmos_portafolios.md](03_catalogo_algoritmos_portafolios.md)
- [04_cambios_implementados.md](04_cambios_implementados.md)
- [06_caracterizacion_instancias.md](06_caracterizacion_instancias.md)
- [07_clasificacion_tamanos.md](07_clasificacion_tamanos.md)
- [08_rendimiento_por_tamano.md](08_rendimiento_por_tamano.md)
- [09_rendimiento_por_caracteristicas.md](09_rendimiento_por_caracteristicas.md)
- [10_especializacion_algoritmica.md](10_especializacion_algoritmica.md)
- [11_comparacion_standalones_portafolios.md](11_comparacion_standalones_portafolios.md)
- [12_analisis_estadistico.md](12_analisis_estadistico.md)
- [13_eficiencia_computacional.md](13_eficiencia_computacional.md)
- [14_complementariedad.md](14_complementariedad.md)
- [15_espacio_objetivos.md](15_espacio_objetivos.md)
- [16_contribuciones_por_brazo.md](16_contribuciones_por_brazo.md)
- [17_analisis_adaptabilidad.md](17_analisis_adaptabilidad.md)
- [18_analisis_recompensas.md](18_analisis_recompensas.md)
- [19_asignacion_presupuesto.md](19_asignacion_presupuesto.md)
- [20_analisis_cooperacion.md](20_analisis_cooperacion.md)
- [21_analisis_combinacion_mecanismos.md](21_analisis_combinacion_mecanismos.md)
- [22_por_que_no_supera_moead.md](22_por_que_no_supera_moead.md)
- [23_eficiencia.md](23_eficiencia.md)
- [24_adaptabilidad.md](24_adaptabilidad.md)
- [25_relacion_objetivos_tesis.md](25_relacion_objetivos_tesis.md)
- [26_resumen_ejecutivo.md](26_resumen_ejecutivo.md)
- [27_guion_reunion.md](27_guion_reunion.md)
- [28_preguntas_respuestas.md](28_preguntas_respuestas.md)
- [29_decisiones_directores.md](29_decisiones_directores.md)
- [30_auditoria_final.md](30_auditoria_final.md)
- [31_limitaciones_y_pendientes.md](31_limitaciones_y_pendientes.md)
- [05_inventario_instancias.csv](05_inventario_instancias.csv)
- [Catálogo de figuras](FIGURAS.md)
- [Referencias](REFERENCIAS.md)
- [Manifest de evidencia](evidence_manifest.json)

## Tablas procesadas

- [algorithm_by_size.csv](tables/algorithm_by_size.csv)
- [allocation_by_stage.csv](tables/allocation_by_stage.csv)
- [archive_overlap.csv](tables/archive_overlap.csv)
- [best_algorithm_by_instance.csv](tables/best_algorithm_by_instance.csv)
- [campaign_inventory.csv](tables/campaign_inventory.csv)
- [directors_decisions.csv](tables/directors_decisions.csv)
- [execution_snapshot_checks.csv](tables/execution_snapshot_checks.csv)
- [exploratory_all_pairwise.csv](tables/exploratory_all_pairwise.csv)
- [exploratory_feature_correlations.csv](tables/exploratory_feature_correlations.csv)
- [feature_performance_scatter.csv](tables/feature_performance_scatter.csv)
- [guidance_events.csv](tables/guidance_events.csv)
- [historical_artifact_catalog.csv](tables/historical_artifact_catalog.csv)
- [historical_auc_recomputed.csv](tables/historical_auc_recomputed.csv)
- [historical_front_metric_checks.csv](tables/historical_front_metric_checks.csv)
- [historical_front_projections.csv](tables/historical_front_projections.csv)
- [historical_runs_separated.csv](tables/historical_runs_separated.csv)
- [historical_standalone_union.csv](tables/historical_standalone_union.csv)
- [historical_summary.csv](tables/historical_summary.csv)
- [hypotheses_evidence.csv](tables/hypotheses_evidence.csv)
- [independent_feature_checks.csv](tables/independent_feature_checks.csv)
- [instance_file_copies.csv](tables/instance_file_copies.csv)
- [instance_inventory_counts.csv](tables/instance_inventory_counts.csv)
- [limitations_missing_information.csv](tables/limitations_missing_information.csv)
- [mode_values.csv](tables/mode_values.csv)
- [objective_ranges.csv](tables/objective_ranges.csv)
- [offline_selector_replay_checks.csv](tables/offline_selector_replay_checks.csv)
- [omnibus_tests.csv](tables/omnibus_tests.csv)
- [p5_selector_sensitivity.csv](tables/p5_selector_sensitivity.csv)
- [p6_injection_fixed_control.csv](tables/p6_injection_fixed_control.csv)
- [p6_injection_pilot.csv](tables/p6_injection_pilot.csv)
- [p7_partial_complete_base_means.csv](tables/p7_partial_complete_base_means.csv)
- [p7_partial_descriptive.csv](tables/p7_partial_descriptive.csv)
- [p7_partial_snapshot.csv](tables/p7_partial_snapshot.csv)
- [passive_union_checks.csv](tables/passive_union_checks.csv)
- [ph_calibration_original_values.csv](tables/ph_calibration_original_values.csv)
- [portfolio_versions.csv](tables/portfolio_versions.csv)
- [profile_relative_effects.csv](tables/profile_relative_effects.csv)
- [profile_relative_effects_by_base.csv](tables/profile_relative_effects_by_base.csv)
- [recent_allocations.csv](tables/recent_allocations.csv)
- [recent_base_means.csv](tables/recent_base_means.csv)
- [recent_blocks.csv](tables/recent_blocks.csv)
- [recent_complementarity.csv](tables/recent_complementarity.csv)
- [recent_final_fronts.csv](tables/recent_final_fronts.csv)
- [recent_metric_checks.csv](tables/recent_metric_checks.csv)
- [recent_paired_by_base.csv](tables/recent_paired_by_base.csv)
- [recent_paired_statistics.csv](tables/recent_paired_statistics.csv)
- [recent_runs.csv](tables/recent_runs.csv)
- [recent_summary.csv](tables/recent_summary.csv)
- [stagnation.csv](tables/stagnation.csv)
- [standalone_per_instance.csv](tables/standalone_per_instance.csv)
- [threshold_baseline_final_hv.csv](tables/threshold_baseline_final_hv.csv)
- [ucb_terms.csv](tables/ucb_terms.csv)

## Reproducción del análisis

Los scripts están en [scripts](scripts/README.md). No ejecutar los runners de optimización antiguos para regenerar este informe. La preservación inicial se captura una sola vez; el verificador final compara hashes sin tocar los originales.

## Ampliación de trazabilidad y línea paralela

- [Preservación y corte inicial](00_preservacion_trazabilidad.md)
- [P5/P6 y P7 parcial externo](32_linea_paralela_P5_P6_P7.md)
- [AUC histórica recalculada](tables/historical_auc_recomputed.csv)
- [Reparto por etapas](tables/allocation_by_stage.csv)
- [Verificación final](evidence/verification.json)
