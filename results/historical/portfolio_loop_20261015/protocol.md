# Protocolo prospectivo — 2026-10-15

Estado inicial: checkout experimental `mojssp`, rama
`experiment/pareto-archive-cooperation`, HEAD `1d695f3`. Es una copia Git
independiente, no un worktree enlazado; todas las escrituras se limitan a este
directorio experimental. No checkout/reset/push ni escrituras en el repositorio
original. Los dos elementos untracked preexistentes se preservan.

El turno previo fue interrumpido: no se encontró proceso Python vivo. La auditoría
actual importa `mojssp` correctamente; el fallo histórico de `pairing` ya no aplica.
Las diez instancias históricas y su split no están disponibles aquí. Los resultados
históricos son contexto descriptivo, no controles para nuevas corridas.

## Presupuesto y datos

Máximo 10 iteraciones; techo de esta campaña: 1.200.000 FE de búsqueda y 45 minutos
de ejecución experimental. Se puede terminar antes con una mejora confirmada;
si se agota el techo, se informa incluso un resultado negativo. Tests y auditoría
de reevaluación de soluciones se contabilizan por separado del presupuesto de
búsqueda y nunca alimentan los algoritmos.

Generador existente `generate_mojssp_instances.InstanceConfig`, semillas de
instancia 81000+índice para desarrollo y 91000+índice para confirmación interna.
No se lee ni se usa el test final del proyecto. Desarrollo: seis bases nuevas
(5x5, 10x10, 20x10, 10x20, 20x20, 30x20), semillas de búsqueda 42,43,44.
Confirmación: ocho bases nuevas, esas seis escalas más 40x20 y 50x50,
semillas 142,143,144. Perfiles balanced, tard_high, nrg_strong, btnk_high,
dur_high y rel_high, predeterminados en manifest.json. No se atribuye causalidad
a características confundidas con tamaño; la dificultad sólo se describe por
progreso, estancamiento y brecha observada.

Cada corrida: 3000 FE reales, población 30, bloque 50, semillas de brazo
seed/seed+1/seed+2 para MOEA/D/NSGA-II/SPEA2. Mismos parámetros nativos que
la línea base, cotas analíticas existentes y referencia HV (1.1,1.1,1.1).
Inicialización incluida, sin generaciones limitantes, warmup neutral 3 bloques
y probes adaptativos originales. Corridas secuenciales; orden de métodos
contrabalanceado por caso. Tiempo de búsqueda incluye archivo, métricas online
y cooperación; análisis final de métricas se cronometra aparte.

## Ciclo y decisiones

Primero cinco controles nuevos: tres individuales, RR uniforme y SW-UCB
W=10,c=.07. I1: padre externo del archivo global cada diez cruces, escogido
por distancia normalizada al archivo local; replay de asignaciones SW-UCB
del control. No reemplaza poblaciones ni altera selección ambiental/descomposición.
Toda descendencia se decodifica y evalúa normalmente: compartir el genotipo no
da FE gratis a la descendencia. El control replay separa cooperación de asignación.

I2 (después de I1): normalizar explotación UCB por máximo de recompensa reciente,
manteniendo W,c, probes y exploración originales. Hipótesis: la escala decreciente
de delta-HV induce exceso de exploración. I3 se formulará por escrito después
de inspeccionar I1/I2; cambiará un mecanismo frente a un padre explícito.
No se combinarán mecanismos sin ablación.

Registrar por bloque HV, delta-HV/FE, tiempo, asignación, rachas sin progreso,
donantes y cruces guiados. Por corrida: HV final y AUC trapezoidal desde (0,0),
cardinalidad de vectores distintos, rango y distancia vecino en objetivos,
distancia genotípica de poblaciones, contribución HV exclusiva leave-one-arm-out
y procedencia de primera observación (no equivale a ascendencia genética).
Guardar genotipos y objetivos finales y de cada brazo para recomputar métricas.

La unidad independiente es la base, promediando semillas antes de inferir.
Reportar diferencias pareadas, W/T/L, intervalos bootstrap de bases y prueba
exacta de signos por permutación; ajustar Holm si hay múltiples candidatos.
No tratar semillas como instancias independientes, ni seleccionar el mejor
individual a posteriori como un competidor deployable (se etiqueta oráculo).

Un candidato pasa a confirmación si mejora HV y AUC medios sin pérdida >10%
en diversidad genotípica media y sin coste temporal >30%, o si presenta un
intercambio calidad/diversidad/tiempo claramente útil y declarado. No se obliga
a 15% de aporte por brazo: reparto de autoría no es diversidad del frente.
Confirmación fija parámetros antes de ejecutar, compara controles idénticos y
se exige mejora HV/AUC en al menos 6/8 bases y CI bootstrap pareado positivo;
además se publican limitaciones de multiplicidad y potencia. Un resultado
inconcluso no cambia el comportamiento predeterminado. No se requiere vencer
a cada individual. Si no hay candidato respaldado, conservar línea base.

## Fundamento consultado

Li, Fialho, Kwong, Zhang (2014), DOI 10.1109/TEVC.2013.2239648:
https://colalab.ai/publications/LiFKZ14.pdf . Ventanas recientes, recompensa
dependiente de escala y equilibrio exploración/explotación; nuestra variante
de escalado no es una reproducción de FRRMAB.

Cooperación con trazabilidad en otro dominio, evidencia contextual sin garantía
para MO-JSSP: https://arxiv.org/abs/2607.13200 . Distinguir explícitamente
intercambio poblacional de unión pasiva; medir homogeneización y costes.
