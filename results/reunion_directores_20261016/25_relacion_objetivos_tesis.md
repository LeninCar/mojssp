# Relación con la pregunta y los objetivos de tesis

La pregunta de investigación se puede sostener como el estudio de **cómo asignación y cooperación afectan la eficiencia y adaptabilidad de un portafolio MO-JSSP**, sin imponer que siempre gane al mejor constituyente.

| Objetivo | Trabajo y evidencia | Estado |
|---|---|---|
| Resolver Cmax, tardanza y energía | Representación común, decoder factible, archivos Pareto, controles individuales | Implementado; optimalidad global desconocida |
| Integrar algoritmos complementarios | Tres brazos pausables, archivos locales/global, MC y solapamiento | Integración y complementariedad observadas |
| Asignar FE inteligentemente | RR, SW-UCB, UCB1/PH y escalado; trazas y ablación I2 | Mejora interna de escala respaldada |
| Compartir información útil | Padre externo, replay y eventos trazables | Señal favorable condicionada; autonomía y crédito pendientes |
| Mejorar eficiencia | HV/AUC a igual FE, tiempo y umbrales con censura | Frente al portafolio original sí; frente a MOEA/D no |
| Adaptarse a instancias | Instancias perfiladas, variación de cuotas y análisis exploratorio | Falta confirmación factorial con bases replicadas |
| Validez y reproducibilidad | Datos preservados, fuente congelada reciente, hashes, semillas, análisis por base | Fuerte para campaña reciente; procedencia histórica parcial |

Los aportes científicos defendibles son: detectar y corregir una desproporción entre explotación y exploración; separar cooperación genética de agregación mediante control de asignación; cuantificar complementariedad con sustitutos preservados; identificar límites de PH y de combinar mecanismos; y diseñar una evaluación que no confunda variantes ni semillas con bases independientes.

La tesis gana precisión al registrar también resultados negativos: mayor diversidad no asegura mayor HV, unión de búsquedas completas no prueba ventaja presupuestaria y combinar mejoras no garantiza aditividad. La auditoría muestra qué preguntas necesitan nuevos controles y evita presentar como resuelta la generalización.

Una redefinición del objetivo hacia “superar siempre a MOEA/D” no está respaldada por los datos ni es necesaria para justificar el estudio. La decisión académica es acordar el alcance de la contribución y un experimento final acotado, con resultados favorables y desfavorables igualmente publicables.
