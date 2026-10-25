# Selección exacta antes de generar nuevas FE

Estado: propuesta, sin autorización de nuevas FE y sin ejecución de optimizaciones.

Recomendación: conservar las seis bases de desarrollo de la campaña actual, que
ya tienen 18 ejecuciones completas, y considerar una sola base adicional para
incluir una victoria standalone observada de SPEA2. Son siete bases identificadas,
con tres semillas nominales por base (42, 43 y 44), no 21 instancias independientes.
Este tamaño es razonable para un piloto descriptivo; no garantiza potencia
estadística ni valida una regla predictiva o una superioridad general.

## Selección y HV medio a 3000 FE

| Instancia | Configuracion | Perfil | MOEAD | NSGAII | SPEA2 | Ganador_medio | Brecha |
| --- | --- | --- | --- | --- | --- | --- | --- |
| development_00_5x5 | 5x5 | {} | 1.078058 | 1.087097 | 1.072508 | NSGA-II | 0.009039 |
| development_01_10x10 | 10x10 | {'tardiness_profile': 'tard_high'} | 0.973701 | 0.972487 | 0.953808 | MOEA/D | 0.001214 |
| development_02_20x10 | 20x10 | {'energy_profile': 'nrg_strong'} | 1.030594 | 0.998664 | 1.003764 | MOEA/D | 0.026830 |
| development_03_10x20 | 10x20 | {'bottleneck_profile': 'btnk_high'} | 0.850390 | 0.838138 | 0.844775 | MOEA/D | 0.005615 |
| development_04_20x20 | 20x20 | {'duration_profile': 'dur_high'} | 0.916823 | 0.886764 | 0.870570 | MOEA/D | 0.030060 |
| development_05_30x20 | 30x20 | {'release_profile': 'rel_high'} | 0.913106 | 0.873190 | 0.886965 | MOEA/D | 0.026142 |
| base_c03_20x10_b04_btnk_high | C3_20x10 | btnk_high | 0.877440 | 0.850255 | 0.872785 | MOEA/D | 0.004654 |

Fuente: tablas `pilot_summary.csv` y `pilot_exact_instances_seeds.csv`; cohortes
separadas. Las primeras seis filas pertenecen a loop_development y la última a
phase2_budget. Todos los HV usan límites analíticos por instancia y referencia
(1.1,1.1,1.1). No se promedian HV entre instancias ni campañas.

Las diferencias pequeñas están representadas por development_01_10x10: brecha
media 0.001214 (aproximadamente 0.125% del HV ganador). Esta proximidad se
describe sin convertir un umbral elegido después de observar los datos en una
prueba de equivalencia. Los controles development_02, 04 y 05 tienen victorias
de MOEA/D en las tres semillas. development_00 tiene ganador medio NSGA-II.
La base adicional tiene victoria de SPEA2 solo en la semilla 42, no en promedio.
Se conservan 43 y 44, donde gana MOEA/D, para evitar mostrar únicamente esa victoria.

## HV exactos por semilla nominal

| Instancia | Semilla | MOEAD | NSGAII | SPEA2 | Ganador |
| --- | --- | --- | --- | --- | --- |
| development_00_5x5 | 42 | 1.087528182 | 1.093934078 | 1.085243786 | NSGA-II |
| development_00_5x5 | 43 | 1.086008794 | 1.072045044 | 1.071241185 | MOEA/D |
| development_00_5x5 | 44 | 1.060636967 | 1.095312042 | 1.061038916 | NSGA-II |
| development_01_10x10 | 42 | 0.977512164 | 0.938274358 | 0.968099186 | MOEA/D |
| development_01_10x10 | 43 | 0.968486068 | 0.981919432 | 0.937864643 | NSGA-II |
| development_01_10x10 | 44 | 0.975105130 | 0.997267032 | 0.955459715 | NSGA-II |
| development_02_20x10 | 42 | 1.034253528 | 1.020182879 | 1.006460651 | MOEA/D |
| development_02_20x10 | 43 | 1.014461552 | 0.996979931 | 0.993859119 | MOEA/D |
| development_02_20x10 | 44 | 1.043066401 | 0.978827896 | 1.010972213 | MOEA/D |
| development_03_10x20 | 42 | 0.858981413 | 0.826586769 | 0.845672297 | MOEA/D |
| development_03_10x20 | 43 | 0.844141558 | 0.865268684 | 0.860209004 | NSGA-II |
| development_03_10x20 | 44 | 0.848046272 | 0.822559064 | 0.828444199 | MOEA/D |
| development_04_20x20 | 42 | 0.921553728 | 0.882398169 | 0.869481814 | MOEA/D |
| development_04_20x20 | 43 | 0.914930912 | 0.877827667 | 0.857027381 | MOEA/D |
| development_04_20x20 | 44 | 0.913985540 | 0.900064853 | 0.885202269 | MOEA/D |
| development_05_30x20 | 42 | 0.901131863 | 0.880709017 | 0.889109113 | MOEA/D |
| development_05_30x20 | 43 | 0.912851692 | 0.878031755 | 0.884794984 | MOEA/D |
| development_05_30x20 | 44 | 0.925335444 | 0.860829377 | 0.886990118 | MOEA/D |
| base_c03_20x10_b04_btnk_high | 42 | 0.865202767 | 0.862332158 | 0.874551385 | SPEA2 |
| base_c03_20x10_b04_btnk_high | 43 | 0.896413020 | 0.834069899 | 0.878634296 | MOEA/D |
| base_c03_20x10_b04_btnk_high | 44 | 0.870702745 | 0.854362303 | 0.865169929 | MOEA/D |

En la campaña actual, la semilla n alimenta MOEA/D con n, NSGA-II con n+1 y
SPEA2 con n+2, tanto en standalone como en portafolio. La campaña histórica usa
otra asignación interna. Igual número nominal no implica igual flujo aleatorio
entre campañas. Los HV históricos no son controles pareados de un futuro run actual.

## Identidades, perfiles y bases

Las seis development_XX son casos del generador 1.0.0, semillas 81000 a 81005,
con dimensiones y perfiles indicados. La base adicional es
base_c03_20x10_b04, perfil btnk_high, configuración C3_20x10; el archivo pertenece
a development según budget_config.json. Su SHA-256 es
b6eacdbc91c3c571fc62f770e3818d7a859ccdb4f8ec21c8c971a55b9c947b1c.
Se verificó su ruta en ../mojssp-dmab/data/generated/expanded_200/, sin escribir allí.

`identity_checks.csv` registra las rutas absolutas, hashes de archivo, rutas
tecnológicas y estructura de operaciones. Los siete casos elegidos tienen IDs
de base distintos y rutas tecnológicas diferentes; no son perfiles repetidos
de una misma base. Esto comprueba identidad y estructura, no independencia
estadística general entre familias de generadores.

Los candidatos base_c01_5x5_b03 y base_c01_5x5_b05_tard_med se verificaron y se
documentan en candidate_identity.json. Son bases distintas (c01_b03 y c01_b05);
el segundo es una variante tard_med de b05. No se incluyen en la extensión mínima
porque ya hay un caso NSGA-II 5x5, y ninguno agrega una victoria de SPEA2.
Sus resultados completos se conservan en historical_standalones.csv. No se
interpretan tres perfiles de una base como tres bases independientes.

## Coste y decisión

1. **Piloto retrospectivo disponible: 0 FE nuevas.** Seis bases × tres semillas,
   18 portafolios y 54 standalones existentes. Ya responde si cambia la contribución
   entre instancias y semillas. Presupuesto histórico reutilizado: 216000 FE,
   sin repetirlo ni contabilizarlo como coste nuevo.
2. **Extensión de atribución solamente: 9000 FE nuevas.** Una base adicional ×
   tres semillas × un UCB escalado × 3000 FE. Los standalone históricos sirven
   únicamente como antecedentes descriptivos; no como control pareado actual.
3. **Extensión controlada recomendada si se aprueba experimentar: 36000 FE nuevas.**
   La misma base × tres semillas × (tres standalones actuales + UCB escalado)
   × 3000 FE: 27000 FE standalone y 9000 FE portafolio. Esto permite comparar
   dentro de una cohorte nueva con las mismas implementaciones y flujos pareados.
   La victoria histórica de SPEA2 no garantiza una victoria en esta nueva cohorte.

Se preservan W=10, c=0.07, población 30, bloques 50, ΔHV, límites analíticos,
referencia (1.1,1.1,1.1), operadores e inicialización. Cada ejecución del portafolio
tiene 3000 FE totales, no 3000 por brazo. Se guardarán archivos locales completos,
frente global, genotipos, schedules, bloques y hashes. No se exige que el ganador
por MC coincida con standalone, ni que SPEA2 gane. No se ajustará el selector.

**No se ejecutará ninguna de las extensiones sin autorización explícita.**
