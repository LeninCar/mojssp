# Por qué la combinación no añade una mejora demostrada

I3 agrega el mismo padre externo a UCB escalado y utiliza decisiones online. A diferencia del tratamiento de guía aislado, no necesita un control previo de asignaciones. La comparación causal primaria de esta iteración es combinado − escalado, con igual FE, operadores y seis bases de desarrollo × tres semillas.


| metric | n_bases | mean_delta | ci_low | ci_high | wins | losses | p_signflip |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hv | 6 | -0.001742 | -0.007521 | 0.003813 | 3 | 3 | 0.562500 |
| auc_hv | 6 | -0.002773 | -0.008144 | 0.002597 | 2 | 4 | 0.406250 |
| seconds | 6 | -0.666759 | -1.642065 | 0.213045 | 3 | 3 | 0.406250 |
| unique_vectors | 6 | -0.833333 | -5.777778 | 5.555556 | 2 | 4 | 0.875000 |
| archive_size | 6 | -2.166667 | -6.222222 | 2.277778 | 2 | 4 | 0.468750 |
| mean_nn_distance | 6 | -0.000108 | -0.000929 | 0.000626 | 3 | 3 | 0.781250 |
| genetic_diversity | 6 | 0.010187 | 0.001645 | 0.018182 | 4 | 2 | 0.125000 |


El ΔHV medio es −.001742, IC que incluye cero, tres bases favorables y tres desfavorables. ΔAUC es −.002773, favorable en dos de seis bases. La diversidad genética media sube ligeramente, mientras HV y cardinalidad no acreditan una ganancia. Se decidió **no adoptarlo ni llevarlo a confirmación**, no declarar que siempre perjudica.

Hay una interacción real en el flujo: el padre externo cambia hijos, archivos y recompensas; escalado convierte esas recompensas en decisiones que alteran qué algoritmo recibe más profundidad. La ganancia condicional de guía con replay no se puede sumar algebraicamente a la ganancia de escalado. El resultado combinado no sigue la misma asignación que ninguno de los controles.

Hipótesis pendientes: donantes distantes poco útiles bajo la nueva asignación; cambios de crédito que desvían FE; información redundante después de que escalado profundiza el brazo fuerte; o incertidumbre estocástica con pocas bases. Ninguna se identificó mediante un factorial completo con replay común a las cuatro celdas. No elegir retrospectivamente sólo las bases favorables ni ajustar la cadencia usando confirmación.

Un siguiente ensayo debe acordar una ablación con asignación común: sin guía y con guía bajo trazas fijas SW-UCB y escalado, más políticas online claramente diferenciadas. Contar el coste de las trazas externas. Primero definir un objetivo de mecanismo (convergencia, región o diversidad), luego elegir métricas primarias y tamaño de muestra. Ese ensayo se propone para después de la reunión.
