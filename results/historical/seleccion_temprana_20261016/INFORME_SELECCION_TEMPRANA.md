# Ganadores por instancia y viabilidad de selección temprana

Auditoría adicional, 16 de octubre de 2026. **0 FE nuevas; sin modificaciones de algoritmos ni apertura de holdout.** No se implementó ni ejecutó probe-and-commit. Las salidas autoritativas están en `tables/v2/` y `figures/v1/`; la auditoría anterior se conserva intacta. Los archivos `v1` son un cálculo intermedio preservado: `v2` distingue correctamente el coste cero de recomendar siempre MOEA/D del coste de observar tres brazos.

## 1. Alcance, fuentes y comparabilidad

| cohort | split | n_instances | n_bases | n_seeds | budgets | standalone_rows | trajectory_rows | min_checkpoint_FE | max_checkpoint_FE |
|---|---|---|---|---|---|---|---|---|---|
| loop_confirmation | confirmation | 8 | 8 | 3 | 3000 | 72 | 4320 | 50.000000 | 3000.000000 |
| loop_development | development | 6 | 6 | 3 | 3000 | 54 | 3240 | 50.000000 | 3000.000000 |
| p7_1000 | development | 10 | 10 | 5 | 1000 | 150 | 3000 | 50.000000 | 1000.000000 |
| phase1_profiles | development | 40 | 8 | 5 | 1000 | 600 | 0 | NA | NA |
| phase2_budget | development | 10 | 10 | 3 | 1000;3000;5000 | 270 | 9000 | 50.000000 | 5000.000000 |
| phase2_pilot | development | 10 | 10 | 3 | 1000 | 90 | 1800 | 50.000000 | 1000.000000 |
| technical_benchmark | development | 8 | 8 | 1 | 1000 | 24 | 0 | NA | NA |


Se reunieron **1260 registros finales standalone**, **420 ternas por instancia/semilla/presupuesto**, **112 celdas de medias por instancia/cohorte/presupuesto** y **21.360 checkpoints**. Estos conteos no representan 420 o 112 bases independientes: incluyen presupuestos relacionados, perfiles de una base y campañas duplicadas. Las cohortes nunca se agrupan para estimar un rendimiento global.

El piloto Fase 2 tiene 90/90 trayectorias standalone idénticas a los prefijos de 1000 de la campaña presupuestaria. Se muestra por separado y no aumenta el tamaño muestral de ésta. El benchmark técnico también reproduce algunos valores de calidad de Fase 1. Las campañas legacy con otros brazos no permiten una terna comparable de los tres actuales y no se introducen en estas decisiones. El catálogo previo de campañas sigue disponible en la auditoría principal.

Fuentes crudas: JSON recientes con un único brazo; `budget_checkpoints.csv`, `pilot_checkpoints.csv`; resúmenes y CSV canónico de bloques P7; CSV finales Fase 1/benchmark. P7 se lee del snapshot fijo ya preservado, no del observador de procedencia con HV cero. La matriz de origen conserva archivo, run_id, instancia, semilla, presupuesto, cohorte y limitaciones. Los hashes de entradas están en [analysis_manifest](evidence/v2/analysis_manifest.json).

El valor final reportado se conserva como `hv_reported`. Cuando el último checkpoint guarda más precisión, se utiliza `hv` de ese checkpoint para mantener consistencia entre líder terminal y ganador; se guardan ambos archivos y `endpoint_minus_reported`, con diferencia ≤5.1×10⁻⁹. No se altera ningún resultado original ni se reconstruyen datos individuales a partir de medias.

## 2. Ganadores finales: muestra completa, no sólo éxitos alternativos

| cohort | budget | MOEA/D | NSGA-II | SPEA2 |
|---|---|---|---|---|
| loop_confirmation | 3000 | 7 | 0 | 1 |
| loop_development | 3000 | 5 | 1 | 0 |
| p7_1000 | 1000 | 5 | 5 | 0 |
| phase1_profiles | 1000 | 28 | 6 | 6 |
| phase2_budget | 1000 | 6 | 3 | 1 |
| phase2_budget | 3000 | 8 | 2 | 0 |
| phase2_budget | 5000 | 7 | 3 | 0 |
| phase2_pilot | 1000 | 6 | 3 | 1 |
| technical_benchmark | 1000 | 5 | 0 | 3 |


Fase 1 tiene 40 variantes correlacionadas de ocho bases; los conteos de la tabla son instancias/variantes, no 40 unidades independientes. En cada celda se elige por HV medio de semillas; la tabla por semilla conserva cambios de ganador y diferencias. Hay **35 celdas** donde NSGA-II o SPEA2 superan a MOEA/D en media, contando todas las cohortes/presupuestos con sus duplicaciones explícitas; no son 35 bases independientes ni un subconjunto usado para inferir superioridad.

Ejemplos recientes completos: desarrollo5×5 lo gana NSGA-II en media (+.009039 sobre MOEA/D); confirmación5×5 lo gana SPEA2 (+.022001), con NSGA-II también por encima de MOEA/D (+.020022). Las restantes bases recientes no se ocultan: en confirmación MOEA/D gana las otras siete medias, y en desarrollo las otras cinco. Algunas semillas individuales cambian de ganador aunque la media sea favorable a MOEA/D.

Tablas principales:

- [winners_by_seed](tables/v2/winners_by_seed.csv): los tres HV, ganador/conjunto de empate, segundo, brecha y diferencias frente a MOEA/D para las 420 ternas.
- [winners_by_instance](tables/v2/winners_by_instance.csv): medias, DE/mínimo/máximo entre semillas de cada algoritmo, victorias estrictas y variación del ganador.
- [all_instance_winners_with_alternative_flags](tables/v2/all_instance_winners_with_alternative_flags.csv): las 112 celdas completas con indicadores de ventaja alternativa.
- [alternative_advantage_navigation](tables/v2/alternative_advantage_navigation.csv): sólo una vista de navegación de esos casos, nunca la muestra inferencial.
- [winners_by_base_with_provenance](tables/v2/winners_by_base_with_provenance.csv): medias de perfiles tras promediar semillas. No crea una instancia física nueva ni considera perfiles independientes.

**Empates prácticos.** Se usa ε=10⁻¹² para empate numérico en el registro y sensibilidades descriptivas fijas de brecha ≤.001, ≤.005 y ≤.010 HV. No son pruebas de equivalencia ni márgenes validados. Por ejemplo, confirmación5×5 tiene sólo .001979 entre SPEA2 y NSGA-II; desarrollo10×10 tiene .001214 entre sus dos mejores medias. Las DE y cambios entre semillas deben acompañar cualquier nombre de “ganador”. La resolución histórica de CSV limita lo que puede afirmarse sobre brechas diminutas.

## 3. Qué rendimiento temprano se puede recuperar

Se dispone de checkpoints observados cada 50 FE: loop hasta3000, Fase 2 presupuesto hasta5000, piloto hasta1000 y P7 hasta1000. Los tres algoritmos están completos en cada corte disponible. Se recuperaron exactamente 100,200,300,500,1000 y3000 cuando el horizonte lo permite. Fase 1 y benchmark sólo ofrecen finales: allí no hay líder temprano inferible. P7 y piloto no permiten consultar3000.

Cada fila en [early_leaders_and_final_winners](tables/v2/early_leaders_and_final_winners.csv) entrega los seis HV (tres al corte y tres al final), líder, ganador, brechas, coste, error y si el líder acaba estrictamente peor. [cut_availability](tables/v2/cut_availability.csv) incluye también todas las combinaciones ausentes, con motivo; no se imputan ni interpolan cortes faltantes.

Se separa el horizonte objetivo: Fase 2 permite final1000,3000 y5000 sobre la misma trayectoria; no son tres réplicas. Un corte igual al presupuesto final es un **control de identidad**, no predicción temprana. Para A, consultar el propio final produce 100% de acierto por construcción.

**Coste de información:** c FE por cada brazo =3c FE de prueba. A B=3000, c=100/200/300/500 consume300/600/900/1500; c=1000 agota B y c=3000 costaría9000. En P7, c=500 ya cuesta1500 y no cabe en una política de1000. Se muestran observaciones retrospectivas sobrepresupuestarias porque existen, pero se rotulan como no viables para prueba+continuación. El baseline E no necesita observar brazos y tiene coste de decisión cero.

## 4. Criterios y ausencia de filtración temporal

| Código | Decisión usando sólo datos hasta c | Interpretación |
|---|---|---|
| A | argmax HVᵢ(c) | Calidad local acumulada |
| B0 | argmax [HVᵢ(c)−HVᵢ(0)], HVᵢ(0)=0 | Matemáticamente idéntico a A si se contabiliza toda inicialización |
| B50 | argmax [HVᵢ(c)−HVᵢ(50)] | Mejora desde el primer checkpoint guardado; no es una población inicial gratuita |
| C | argmax [HVᵢ(c)−HVᵢ(max(0,c−100))] / [c−max(0,c−100)] | Ventana reciente fija de100 FE; a c=100 coincide con A |
| D | Elegir A sólo si brecha líder−segundo ≥.005; en otro caso MOEA/D | Fallback completo, no acierto condicionado sólo a los casos fáciles |
| E | Siempre MOEA/D | Referencia trivial sin FE de prueba |

El margen y la ventana se fijaron en [protocol.json](evidence/protocol.json) antes del nuevo análisis temprano y no se optimizan sobre confirmación o holdout. Son decisiones descriptivas, no una preregistración de una futura campaña confirmatoria ni una selección de hiperparámetros ganadora. Los empates se rompen MOEA/D→NSGA-II→SPEA2 y se registra cuántos candidatos empatan.

La decisión no consulta el HV final. Éste se usa exclusivamente después para determinar acierto, error y regret=HV(mejor standalone a B)−HV(standalone recomendado a B). Esa puntuación retrospectiva **no es el resultado de ejecutar la política a coste B**, porque observar tres brazos consume recursos.

## 5. Evidencia de desarrollo para C1: 200 FE por brazo

Loop desarrollo, 6 bases independientes, tres semillas por base, objetivo3000. Las semillas se promedian dentro de base; los IC son bootstrap percentil de20.000 remuestreos de bases, semilla analítica20261016, sin tratar18 semillas como18 bases.

| criterion | n_bases | n_decisions | accuracy | accuracy_ci_low | accuracy_ci_high | mean_regret | regret_ci_low | regret_ci_high |
|---|---|---|---|---|---|---|---|---|
| A_local_HV | 6 | 18 | 0.333333 | 0.111111 | 0.555556 | 0.016560 | 0.010529 | 0.023103 |
| B0_gain_from_zero | 6 | 18 | 0.333333 | 0.111111 | 0.555556 | 0.016560 | 0.010529 | 0.023103 |
| B50_gain_after_first_checkpoint | 6 | 18 | 0.333333 | 0.166667 | 0.500000 | 0.019159 | 0.013661 | 0.024821 |
| C_recent_100_FE_slope | 6 | 18 | 0.166667 | 0.000000 | 0.388889 | 0.019542 | 0.015287 | 0.022637 |
| D_margin_005_fallback_MOEAD | 6 | 18 | 0.500000 | 0.277778 | 0.666667 | 0.012451 | 0.009293 | 0.016409 |
| E_always_MOEAD | 6 | 18 | 0.722222 | 0.444444 | 0.944444 | 0.005434 | 0.001174 | 0.010303 |


A identifica6/18 ganadores frente a13/18 para siempre MOEA/D. Su regret medio es .016560 frente a .005434. El regret adicional de A sobre E es +.011126, IC exploratorio por base [.003947,.019314]; no se presenta como nueva prueba confirmatoria entre todos los horizontes/criterios examinados. B50 no mejora el acierto y C sólo acierta3/18. D eleva A a9/18, pero sigue por debajo de E y con mayor regret. A y B0 no son dos evidencias independientes.

**Sí: el ganador temprano puede terminar siendo el peor.** A200 lo hace en6/18 casos de desarrollo. Estos son todos esos casos en el corte pertinente:

| instance | seed | leader | final_winner | local_gap_best_second | leader_final_regret |
|---|---|---|---|---|---|
| development_01_10x10 | 44 | SPEA2 | NSGA-II | 0.017264 | 0.041807 |
| development_02_20x10 | 43 | SPEA2 | MOEA/D | 0.023182 | 0.020602 |
| development_03_10x20 | 42 | NSGA-II | MOEA/D | 0.027398 | 0.032395 |
| development_03_10x20 | 44 | NSGA-II | MOEA/D | 0.004527 | 0.025487 |
| development_04_20x20 | 44 | SPEA2 | MOEA/D | 0.006283 | 0.028783 |
| development_05_30x20 | 42 | NSGA-II | MOEA/D | 0.003416 | 0.020423 |


La carpeta conserva todos los errores de las demás cohortes, horizontes y semillas; no se calcula una frecuencia global sumando cortes dependientes. Ver [initial_leader_final_worst_cases](tables/v2/initial_leader_final_worst_cases.csv).

## 6. ¿Esperar más corrige la señal?

| cut_per_arm | criterion | accuracy | mean_regret | total_probe_FE | feasible_probe_with_continuation |
|---|---|---|---|---|---|
| 100 | A_local_HV | 0.555556 | 0.010149 | 300 | True |
| 100 | D_margin_005_fallback_MOEAD | 0.666667 | 0.005128 | 300 | True |
| 100 | E_always_MOEAD | 0.722222 | 0.005434 | 0 | True |
| 200 | A_local_HV | 0.333333 | 0.016560 | 600 | True |
| 200 | D_margin_005_fallback_MOEAD | 0.500000 | 0.012451 | 600 | True |
| 200 | E_always_MOEAD | 0.722222 | 0.005434 | 0 | True |
| 300 | A_local_HV | 0.333333 | 0.019339 | 900 | True |
| 300 | D_margin_005_fallback_MOEAD | 0.555556 | 0.009945 | 900 | True |
| 300 | E_always_MOEAD | 0.722222 | 0.005434 | 0 | True |
| 500 | A_local_HV | 0.277778 | 0.018710 | 1500 | True |
| 500 | D_margin_005_fallback_MOEAD | 0.555556 | 0.010321 | 1500 | True |
| 500 | E_always_MOEAD | 0.722222 | 0.005434 | 0 | True |
| 1000 | A_local_HV | 0.388889 | 0.015572 | 3000 | False |
| 1000 | D_margin_005_fallback_MOEAD | 0.611111 | 0.009666 | 3000 | False |
| 1000 | E_always_MOEAD | 0.722222 | 0.005434 | 0 | True |


En desarrollo, A100 acierta55.6%, A20033.3%, A30033.3%, A50027.8% y A100038.9%, frente a72.2% de E. **La señal no mejora monótonamente esperando más.** El punto de menor regret de un criterio no se elige automáticamente como nuevo hiperparámetro después de inspeccionar múltiples opciones. D100 tiene regret .005128 frente a .005434 de E, pero diferencia −.000305 con IC exploratorio [−.004876,.003437]; no respalda declarar un ganador ni adoptar100 FE.

Confirmación se reporta sólo descriptivamente: A200 acierta50% frente a62.5% de E. A1000 alcanza66.7%, pero costaría3000 FE de prueba sin continuación. No se utiliza ese resultado para seleccionar un nuevo corte. P7 a final1000 ofrece A50066% frente a48% de E, pero la prueba de tres brazos costaría1500, superior a su presupuesto final. No es evidencia de una política viable a1000 ni autorización para transferir el corte a otra cohorte.

La estabilidad es observada, no latente: [leader_stability_by_run](tables/v2/leader_stability_by_run.csv) conserva las secuencias entre cortes y el primer corte tras el cual el ganador final permanece líder **entre puntos guardados**. Ese primer corte usa futuro descriptivamente y no puede convertirse en regla online. [leader_transitions](tables/v2/leader_transitions.csv) y [confusión líder→ganador](tables/v2/leader_final_confusion_counts.csv) muestran errores sin ocultar reversiones.

## 7. Características estructurales y ganadores

Se añadieron J, M, operaciones, J/M, CV y cociente máximo/media de carga (proxy de cuello de botella), CV de procesamiento, holgura, releases, contraste energético, correlación tiempo–energía y modos. Sólo se usaron descriptores ya calculados de instancias no reservadas. Fuente: [structural_features_and_performance_gaps](tables/v2/structural_features_and_performance_gaps.csv).

Se exploran diferencias NSGA-II−MOEA/D y SPEA2−MOEA/D, no correlaciones aisladas con HV absoluto. Cada cohorte y presupuesto permanece separado. Para Fase 1 se usan sólo perfiles nominales al correlacionar características entre bases; los otros perfiles se conservan en las tablas completas. No se cuentan40 perfiles como40 bases. [exploratory_structural_associations](tables/v2/exploratory_structural_associations.csv) registra n, constantes y límites.

No se ajustó modelo ni se seleccionaron características. Con6/8 bases loop y confusión tamaño/perfil no se identifica una regla general; las cohortes contemporáneas tienen cinco modos constantes. El hecho de que alternativas ganen algunos casos pequeños no prueba especialización por tamaño. La señal de cuello de botella de la auditoría previa sigue siendo una hipótesis para bases nuevas, no explicación causal de las reversiones tempranas.

## 8. ¿Qué recomienda realmente UCB escalado?

| split | criterion | n_bases | n_runs | accuracy | mean_regret |
|---|---|---|---|---|---|
| confirmation | most_FE | 8 | 24 | 0.458333 | 0.014566 |
| confirmation | reward_all | 8 | 24 | 0.625000 | 0.005841 |
| confirmation | reward_no_warmup | 8 | 24 | 0.458333 | 0.014566 |
| confirmation | final_marginal | 8 | 24 | 0.458333 | 0.014566 |
| development | most_FE | 6 | 18 | 0.555556 | 0.010740 |
| development | reward_all | 6 | 18 | 0.722222 | 0.005434 |
| development | reward_no_warmup | 6 | 18 | 0.555556 | 0.010740 |
| development | final_marginal | 6 | 18 | 0.555556 | 0.010740 |


Se cotejan las42 corridas escaladas con sus standalone del mismo caso y semilla. Mayor FE, mayor recompensa **sin warmup** y mayor MC final coinciden aquí en el brazo elegido; coincidir entre criterios no significa ser correcto frente al mejor standalone. En confirmación esas recomendaciones aciertan45.8%, frente a62.5% de siempre MOEA/D. El crédito incluyendo warmup suele favorecer MOEA/D porque empieza con archivo vacío; no es el mismo crédito que actualiza UCB.

Son criterios ex post, con FE locales desiguales y crédito global dependiente del orden/archivo. El mejor standalone a B ha recibido todo B; el brazo de portafolio sólo parte de él. Contribución marginal final mide exclusividad en la unión, no capacidad de convergencia a presupuesto completo. Recompensa temprana puede terminar cubierta/dominada. No se atribuyen estos desacuerdos a una causa única ya demostrada. Las comparaciones por corrida y sus fuentes están en [scaled_portfolio_recommendations](tables/v2/scaled_portfolio_recommendations.csv).

## 9. Qué se puede estimar sin piloto y qué no

Se estimaron retrospectivamente acierto, regret, brechas, estabilidad y casos líder→peor sin FE nuevas. Las trayectorias también permiten consultar el **HV del brazo elegido** en su horizonte local coste-factible: con prueba c por brazo y presupuesto total B, el elegido termina en B−2c FE locales. Para C1, B=3000,c=200 da2600, no3000. E no hace prueba y llega a3000.

La tabla [cost_feasible_selected_only_proxy](tables/v2/cost_feasible_selected_only_proxy.csv) muestra ese lookup, condicionado a que el flujo pasivo conserve idéntico estado/RNG. En desarrollo A200 entrega un HV seleccionado-solo medio .020302 por debajo de MOEA/D3000. Retener los otros archivos puede añadir volumen: el lookup y max(HV elegido, HV de prueba) son **cotas inferiores**, no la calidad exacta de la unión final. Una cota inferior negativa no demuestra que toda la política sea peor. No se ejecutó ni implementó un selector C1 para producir esos valores.

Para comprobar calidad total, AUC de la política y tiempo hace falta guardar o ejecutar la continuación real: población/RNG por brazo, archivos de prueba y frente final, FE reales incluido arranque, mantenimiento de archivo y cronometraje. Los HV escalares no determinan el HV de una unión de frentes. La validación de generalización requiere además bases nuevas y decisiones fijadas antes de evaluarlas.

| cohort | missing | why_it_matters | how_to_obtain | when |
|---|---|---|---|---|
| phase1_profiles | Early HV at 100/200/300/500; intermediate individual front/trace | Only final records/fronts exist; no inference from means | Recover old trace if separately archived; otherwise new controlled run would be necessary | Before C1: cannot use phase1 to calibrate early signals |
| technical_benchmark | Early trajectory | Final-only benchmark; some quality values duplicate phase1 | Same as phase1; do not treat as new independent evidence | No new run required for this report |
| p7_1000 | Local HV at 3000; independent final at 3000 | Runs stop at 1000; 500 per arm costs 1500 and is over budget for a 1000 policy | Separate approved larger-budget experiment, same source/configuration | After methodological review |
| loop_and_phase2 | Exact union front after choosing one arm and continuing | Local scalar trajectories exist, but fronts at arbitrary local FE are absent | Actual pilot export of selected state, prefix archives and final union; or recovery of complete archived data | Necessary to prove final policy quality, not winner accuracy |
| all | Actual wall time and exact FE calls for probe-and-commit | No such execution exists; standalone lookup omits bookkeeping/state-transfer effects | Instrument evaluator calls, populations/RNG states and wall clock in a new limited pilot | Only after approval |
| all | Validated predictor for new base families | Small independent n; profiles correlated; contemporary modes constant | New crossed bases, grouped validation and fixed success criteria | Not inferred from this audit |
| all | Scientifically agreed practical tie and margin | 0.001/0.005/0.010 are fixed descriptive sensitivities, not validated equivalence thresholds | Agree margin before a confirmatory experiment; do not tune on confirmation | Before claiming practical equivalence or definitive selector |
| phase2_pilot | Independent replication beyond budget cohort | 90/90 standalone pilot trajectories equal 1000-FE budget prefixes | No extra data needed to recognize duplication; do not add sample sizes | Already checked |


## 10. Recomendación metodológica antes de C1

**Revisar la justificación del criterio A200; no avanzar automáticamente al piloto como si hubiera una señal prometedora demostrada.** La evidencia de desarrollo es desfavorable para identificar al mejor standalone mediante máximo HV a200. Tampoco proporciona una justificación robusta para sustituir200 por100,300,500 o1000; aumentar observación no garantiza mejor selección y puede consumir la continuación.

Dos alternativas para revisar con los directores:

1. Mantener200 por brazo únicamente como **piloto técnico/de falsificación** con 600 FE de prueba +2400 de continuación, comparadores MOEA/D, uniforme y escalado, presupuesto exacto y registro de estados. El criterio conserva una hipótesis cuestionada; n=2 bases no justificaría validación de eficacia. No cambiar umbral/corte usando confirmación.
2. Posponer C1 de eficacia y decidir primero qué señal o condición de heterogeneidad merece un contraste nuevo, con bases de desarrollo nuevas y protocolo limitado. No desplegar un selector definitivo ni lanzar un barrido de cortes/umbrales sobre las mismas bases hasta encontrar uno favorable.

La revisión que justifican los datos es conceptual y metodológica, no una selección retrospectiva de un nuevo presupuesto ganador. La decisión de ejecutar, modificar o cancelar C1 queda pendiente. Esta tarea se detiene aquí, con cero FE nuevas.

![Acierto retrospectivo por cohorte, con coste y zonas sin continuación](figures/v1/01_acierto_por_corte.png)

Acierto retrospectivo por cohorte, con coste y zonas sin continuación. Fuentes, unidades, población y hashes: [manifiesto de figuras](figures/v1/figure_manifest.json).

![Criterios evaluados sólo en desarrollo para discutir C1](figures/v1/02_matriz_desarrollo.png)

Criterios evaluados sólo en desarrollo para discutir C1. Fuentes, unidades, población y hashes: [manifiesto de figuras](figures/v1/figure_manifest.json).

![Ejemplos de trayectorias: cuatro casos ilustrativos de desarrollo](figures/v1/03_trayectorias_representativas.png)

Ejemplos de trayectorias: cuatro casos ilustrativos de desarrollo. Fuentes, unidades, población y hashes: [manifiesto de figuras](figures/v1/figure_manifest.json).

![Transiciones entre líder200 y ganador3000](figures/v1/04_transiciones_lider_ganador.png)

Transiciones entre líder200 y ganador3000. Fuentes, unidades, población y hashes: [manifiesto de figuras](figures/v1/figure_manifest.json).

![Recomendación final del portafolio versus ganador standalone](figures/v1/05_portafolio_y_standalone.png)

Recomendación final del portafolio versus ganador standalone. Fuentes, unidades, población y hashes: [manifiesto de figuras](figures/v1/figure_manifest.json).

![Descriptores y brechas relativas, sin regla predictiva](figures/v1/06_caracteristicas_y_ganadores.png)

Descriptores y brechas relativas, sin regla predictiva. Fuentes, unidades, población y hashes: [manifiesto de figuras](figures/v1/figure_manifest.json).
