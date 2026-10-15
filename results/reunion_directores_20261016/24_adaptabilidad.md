# Qué adaptabilidad está respaldada

Conviene distinguir tres propiedades que requieren evidencias diferentes.

| Propiedad | Evidencia disponible | Conclusión |
|---|---|---|
| Adaptación dentro de una corrida | Ventana de recompensas, términos UCB, cambios de brazo y diferencias por etapa | Implementada y observada; el escalado mejora su utilidad frente al control |
| Adaptación entre instancias | Cuotas distintas, ganadores distintos y respuestas de perfiles | Heterogeneidad observada; no existe todavía una regla validada basada en rasgos |
| Generalización | Nuevas bases de confirmación del mismo generador y perfiles por tamaño | Confirmación interna limitada; test final y familias externas pendientes |

El reparto desigual no basta: se exige que cambiar la política produzca una mejora bajo controles. I2 ofrece esa evidencia frente a SW-UCB original, con las ocho bases favorables. La reconstrucción de recompensas respalda que el mecanismo usa progreso reciente. Aun así, no demuestra que seleccione el mejor brazo posible en cada etapa: ese oráculo exige contrafactuales que no se ejecutaron.

La primera base pequeña asigna recursos y tiene ganadores distintos; la mayor parte del resto favorece MOEA/D. La relación con características no es causal porque perfil y geometría se confunden en la campaña reciente. Las correlaciones históricas tampoco se mantienen necesariamente al cambiar B. Por eso “adaptativo” describe una regla dependiente de observaciones, no una garantía de generalización.

PH detecta disminución de una señal global, pero esa señal disminuye naturalmente al refinar el archivo y depende de los algoritmos ejecutados antes. Sus alarmas no prueban cambios reales de régimen ni identificación de un nuevo mejor brazo. El resultado negativo respalda una decisión de parsimonia y sugiere estudiar escala del crédito antes de añadir más detectores.

Ver [selección](17_analisis_adaptabilidad.md), [recompensas](18_analisis_recompensas.md), [presupuesto](19_asignacion_presupuesto.md). Mantener intacto el holdout final es necesario para una futura afirmación de generalización.
