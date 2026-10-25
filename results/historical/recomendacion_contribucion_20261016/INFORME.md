# Recomendación retrospectiva por contribución marginal

Se analizaron las seis instancias de desarrollo de la campaña del 15 de octubre,
con tres semillas cada una. No se generaron nuevas FE ni se abrió el holdout.
Se añadió una salida posterior a la búsqueda, sin conectar código al selector
ni cambiar los algoritmos. La propuesta de extensión queda pendiente de aprobación.

## Resultado principal

La salida «algoritmo con mayor contribución marginal al frente obtenido» cambia:
MOEA/D recibe 8 recomendaciones, NSGA-II 7 y SPEA2 3 entre 18 ejecuciones.
Las seis instancias cambian de recomendación entre semillas. No hay empates
numéricos entre máximos ni ejecuciones con las tres contribuciones nulas.
Esto no constituye una recomendación estable del mejor algoritmo para una base.

En 16 ejecuciones solo un brazo tiene MC positiva; en dos tienen MC positiva dos
brazos: development_02_20x10/43 y development_03_10x20/42. La existencia de un
ganador MC no prueba cooperación activa: esta configuración scaled solo agrega
archivos y asigna recursos mediante UCB. No intercambia padres externos.

![MC por brazo, instancia y semilla](figures/contributions.png)

Figura 1. MC=HV(unión global)−HV(unión de archivos locales de otros brazos),
en HV normalizado, referencia (1.1,1.1,1.1). Desarrollo, 3000 FE, seis bases ×
tres semillas. Los datos provienen de los JSON crudos listados en recommendations.csv.
Las barras cero no afirman que un brazo nunca produjo soluciones útiles.

![Recomendaciones finales](figures/recommendations.png)

Figura 2. Brazo de MC máxima por ejecución, con los mismos datos y presupuesto.
Los colores representan categorías, no calidad relativa entre instancias.

## Definición y tratamiento de procedencia

Para cada brazo a, MC(a)=HV(P_global)−HV(ND(unión de archivos locales b≠a)).
Se usan todos los puntos locales retenidos, incluidos los dominados globalmente
que podrían reaparecer tras retirar a. No se elimina solamente un subconjunto
del frente global. No se suman MC como si representaran el HV total.

La pertenencia al archivo local identifica un brazo que obtuvo/retuvo el genotipo
en esta configuración sin transferencia. No identifica el primer descubridor,
su FE exacta de descubrimiento ni ascendencia genética. En configuraciones con
transferencia, esa interpretación necesitaría otra auditoría; el módulo las rechaza.

Un mismo genotipo en varios brazos conserva todos sus propietarios y permanece
al retirar uno si existe otro propietario. Genotipos distintos con idéntico vector
objetivo también conservan el mismo volumen. Se deduplican coordenadas para HV;
los counts genotípicos y los de vectores se reportan por separado. Las soluciones
dominadas no agregan volumen. No se distribuye arbitrariamente el volumen compartido.
En estos datos finales no se observaron genotipos o vectores globales compartidos
entre archivos locales; los casos compartidos están cubiertos por pruebas sintéticas.

La tolerancia numérica es max(1e-12,1e-10×|HV_global|), establecida para errores de
punto flotante, no calibrada con victorias. Se guarda raw_mc; un negativo diminuto
se trunca a cero y un negativo mayor causa error. Máximos dentro de tolerancia
producen empate; sin MC positiva se informa incertidumbre y recommended_arm=null.
Una procedencia global no verificable causa error explícito: no se inventa dueño
ni se emite recomendación. Las diferencias pequeñas de HV standalone son una
cuestión distinta de los empates numéricos de MC.

## Standalone, recompensas y recursos

La coincidencia descriptiva con el ganador standalone es 10/18; no es una tasa
de corrección de MC. MC responde al frente obtenido con presupuestos parciales
adaptativos; standalone responde a una ejecución de un algoritmo con 3000 FE.
Por ejemplo development_00_5x5/44 recomienda SPEA2 por MC aunque NSGA-II gana
standalone. Esta discrepancia no invalida ninguno de los dos cálculos.

individual_contributions.csv incluye FE por brazo, recompensas acumuladas con y
sin warmup, MC, HV sin el brazo y counts exclusivos/compartidos. Ninguna recompensa
ni número de FE entra en la elección de MC máxima. El crédito inmediato depende
de orden y oportunidades; MC es una retirada retrospectiva sobre archivos finales.
MC cero puede reflejar cobertura o dominancia de otros brazos y no inutilidad histórica.

## Conservación y validación

Se verificaron las 18 ejecuciones: 60 bloques × 50 FE=3000, asignaciones por brazo,
HV global y las 54 MC contra los campos crudos. Los límites analíticos se recalcularon
desde las seis instancias autorizadas y todas las coordenadas normalizadas se
compararon con las almacenadas. Se validaron los 910 genotipos del frente global:
decodificación determinista, restricciones del schedule y objetivos derivados
del schedule coincidentes con los guardados. Esto no llama a Evaluator.evaluate
ni realiza búsqueda; esa función estuvo bloqueada durante todo el procesamiento.

Se reprodujeron las 57 decisiones adaptativas por ejecución (1026 en total) del
selector con la misma semilla y recompensas guardadas. Se verificó cada fuente
registrada en los JSON scaled contra su hash de ejecución: los módulos actuales
coinciden; el runner de desarrollo corresponde al snapshot congelado research_v1,
mientras el runner actual es una revisión posterior. No se confunden esas versiones.
No hay modificaciones
de archivos previamente seguidos en Git, de resultados crudos ni de otros repositorios.
Las nuevas piezas son contribution_report.py, report_portfolio_contribution.py,
test_contribution_report_offline.py y este directorio nuevo de análisis.

Las siete pruebas unitarias pasan: volumen analítico independiente, reaparición
de puntos dominados al retirar un brazo, genotipos compartidos, objetivos iguales
con genotipos distintos, duplicados, empate positivo, presupuestos incorrectos,
cohortes reservadas, procedencia desconocida, IDs falsificados, determinismo e
inmutabilidad de entradas y RNG. Véanse evidence/tests.txt y tables/conservation.csv.

El replay del selector usa feedback guardado: no demuestra por sí solo igualdad
de una nueva trayectoria evolutiva. No se ejecutó una repetición completa, porque
requeriría nuevas FE prohibidas. La conservación está respaldada por fuentes
idénticas, aislamiento del postprocesador, entradas inmutables y replay; una prueba
integral con nueva búsqueda queda pendiente de autorización, no se presenta como hecha.

## Datos faltantes y límites

Los tres candidatos históricos inspeccionados tienen resultados standalone y
objetivos finales, pero no archivos de UCB escalado a 3000 FE con genotipos por brazo.
No se pueden fabricar MC exactas de esos portafolios a partir de standalone o
de simples conteos de procedencia. Se detallan en candidate_identity.json.

Tres semillas no bastan para concluir estabilidad poblacional; seis bases de un
generador y perfiles confundidos con tamaños no prueban especialización causal.
La extensión propuesta está estratificada deliberadamente por resultados conocidos:
es un piloto de variación de atribución, no una muestra imparcial para medir la
frecuencia general de superioridad. No hay apertura ni ajuste sobre confirmation
o holdout. La recomendación es final, no una selección temprana ni probe-and-commit.

## Reproducción y archivos

Desde la raíz del checkout, sin nuevas FE:

```powershell
python -B -X utf8 scripts/report_portfolio_contribution.py --output results/recomendacion_contribucion_REPLICA_NUEVA
$env:PYTHONPATH='src'
python -B -X utf8 -m unittest discover -s tests -p test_contribution_report_offline.py -v
```

El directorio de salida debe ser nuevo: la herramienta se niega a sobrescribir.
La réplica produce tablas, JSON con frentes/schedules y figuras. Este complemento
se generó con scripts/build_supplement.py (también de creación exclusiva).
Versiones de librerías e inputs se registran en evidence. No se necesita cargar
alguna instancia reservada. Los candidatos históricos requieren conservar las
rutas de origen o restaurarlas desde el respaldo histórico ya existente; sus
hashes y rutas están declarados, sin duplicarlos dentro de este informe.

## Índice

- [Lista exacta, HV y costes para aprobación](PROPUESTA_PILOTO_PARA_APROBACION.md).
- [Recomendaciones por ejecución](tables/recommendations.csv).
- [54 contribuciones por brazo](tables/individual_contributions.csv).
- [Estabilidad entre semillas](tables/stability.csv).
- [21 ternas standalone propuestas](tables/pilot_exact_instances_seeds.csv).
- [Identidades y estructura](tables/identity_checks.csv).
- [Auditoría de conservación](tables/conservation.csv).
- [Fuentes históricas](tables/historical_standalones.csv).
- [Protocolo](evidence/protocol.json), [hashes de entrada](evidence/input_hashes.json),
  [pruebas](evidence/tests.txt), [identidad de candidatos](evidence/candidate_identity.json).
- runs/: 18 JSON con frente Pareto completo, procedencia y schedules asociados.

Conclusión: ya existe evidencia descriptiva suficiente, a coste cero FE, de que
el máximo contribuyente cambia entre ejecuciones y entre instancias. No existe
evidencia de una recomendación estable por instancia ni de que MC permita anticipar
el mejor standalone. Cualquier extensión se detiene para revisión y autorización.
