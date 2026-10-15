# Auditoría final y conservación de evidencia

## Cálculos verificados sin optimizar

Se recalcularon HV desde todos los frentes finales recientes, AUC desde bloques y MC desde los archivos locales completos. Se utilizó un algoritmo independiente de unión de cajas por barrido, sin alterar normalización ni referencia. El [registro numérico](evidence/analysis_audit.json) y [recent_metric_checks](tables/recent_metric_checks.csv) muestran:

| Control | Resultado |
|---|---|
| Corridas recientes | 312 |
| Error máximo HV final | 2.22e-16 |
| Error máximo AUC | 4.44e-16 |
| Error máximo MC | 4.44e-16 |
| FE por corrida | Todas 3000, 60 bloques |
| FE de optimización nuevas | 0 |
| Rendimientos holdout utilizados | 0 |
| Características holdout | Sólo metadatos declarados; contenido reservado |

La caracterización vectorizada se comprobó independientemente con el lector de dominio en [independent_feature_checks](tables/independent_feature_checks.csv); diferencia máxima 1.42×10⁻¹⁴. Los hashes originales y el estado Git anterior están en [preservación](evidence/preservation_before.json). La comprobación final de integridad se añade a [verification.json](evidence/verification.json), con diferencias explícitas si las hubiera. No se confunde la auditoría previa de 20131 calendarios con un recálculo de calendarios realizado hoy: ahora se verifican objetivos/frentes guardados, no se reejecutan algoritmos.

## Dependencias y fuentes

Piloto y corte de 1000 FE: 150 pares de HV idénticos. PH C5 calibración/comparación: 30 pares idénticos. Se conservan como cohortes distintas con dependencia declarada, sin sumar evidencia independiente. Los parámetros de semillas internas históricas difieren de la campaña reciente: Fase 2 portafolio usa (s×10007+17/29/43) mod (2³¹−1), individuales usan s; reciente alinea brazos s/s+1/s+2 también para controles individuales. Esto impide atribuir diferencias entre campañas sólo a mecanismos.

Los 50 archivos bajo `data/invalid` conservan errores de lectura documentados; no se infiere su causa ni que fueran intencionales. Los resultados antiguos no tienen todos un commit/código cargado exacto. La campaña reciente preserva instantáneas y una corrección de hashes de la línea base: no se oculta esa limitación mediante HEAD actual.

## Afirmaciones históricas revisadas

1. El cierre PH dice “superior” aunque sus tres contrastes Holm no son significativos: conservar SW-UCB por parsimonia es defendible; superioridad estadística no.
2. La Fase 1 utiliza expresiones de especialización causal/general con una base por geometría: este informe las rebaja a señales exploratorias.
3. La contribución heredada restaba puntos del ND ya filtrado: se usa la definición canónica recuperando sustitutos.
4. Un metadato histórico indica mutación .1, mientras los constructores usados y la instantánea reciente especifican .2 para secuencia y 1/N para modos: se explicita la incertidumbre histórica.
5. “Cotas dinámicas” en un documento PH no significa que el normalizador se reescale durante búsqueda: las cotas de instancia son fijas bajo la implementación auditada.

## Visualización, estadística y trazabilidad

Cada figura identifica cohorte, FE, instancias/semillas y tabla fuente. Para datos estructurales FE no aplica; para la unión se indica coste 3B. Los mapas no mezclan objetivos físicos de bases diferentes. Se revisan visualmente PNG, leyendas y escalas, con SVG para reutilización. La familia principal de dos pruebas es distinta de las exploratorias; cada tabla conserva unidad base. Las figuras 14 y 15 se ajustaron tras inspección para que las barras de color no oculten datos.

El [manifest de evidencia](evidence_manifest.json) enlaza archivos originales, transformaciones y hashes de productos. Esta auditoría no hizo checkout, commit, push ni modificó algoritmos o resultados originales. Sus productos nuevos están en este directorio. Otros procesos sí cambiaron directorios externos, como registra la verificación final. No se instalaron paquetes: CSV/estadística principal usa el Python bundled; gráficos y estadísticas adicionales usan matplotlib/SciPy ya existentes, ausentes del bundle.

## Resultado de la verificación de cierre

Estado: **analysis_verified_external_changes_disclosed**. Se recomprobaron 3377 archivos del inventario inicial. En el checkout de esta tarea: 0 originales modificados/eliminados y 0 archivos nuevos fuera del directorio autorizado. El repositorio original mojssp-dmab conserva sus archivos, rama, HEAD y estado Git. Índice congelado reciente: 530 archivos, 0 discrepancias.

**Incidencia externa:** la copia `mojssp-dmab - copia` desapareció durante la tarea y otro checkout produjo datos P7 y modificó su diseño. Se observan 1860 rutas externas cambiadas/no disponibles y 367 archivos externos nuevos respecto al inventario. No fueron operaciones de esta auditoría. No se certifica preservación global de los directorios externos ni se intenta restaurarlos. El corte adicional P7 se conserva separado y no altera la confirmación principal.

Se verificaron 312 procedencias recientes, 4788 decisiones offline del selector y 42 equivalencias de unión pasiva. Se recalcularon 450 HV de frentes históricos, error máximo 0. Las 270 contribuciones canónicas históricas comparadas tienen error máximo 5e-16. No se encontraron instancias de rendimiento reservadas en las tablas analizadas.

Detalle completo: [verification.json](evidence/verification.json) y [corte adicional](evidence/additional_campaign_cutoff.json).
