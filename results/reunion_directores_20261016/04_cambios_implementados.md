# Qué se modificó, qué se conservó y por qué

Esta auditoría **no implementó cambios algorítmicos**. Reconstruye modificaciones preexistentes y conserva su [diff](evidence/preexisting_algorithm_changes.diff). El checkout inicial tenía modificados `arms.py`, `moead.py` y `spea2.py`, además de `cooperation.py`, scripts y resultados sin seguimiento Git. HEAD por sí solo no representa el experimento.

| Iteración | Limitación e hipótesis | Cambio aislado | Componentes conservados | Resultado / decisión |
|---|---|---|---|---|
| Observabilidad P4 | No era posible seguir identidad de soluciones | IDs y procedencia sin alterar RNG | Decodificador, objetivos y selección | Base `1d695f3`; no equivale a cooperación |
| I1 | Unión pasiva no transmite información genética | Segundo padre extranjero cada diez cruces; asignación reproducida del control | FE, poblaciones, selección ambiental, pesos, decoder | Ganancia media bajo replay; candidato condicionado |
| I2 | Crédito ΔHV pequeño frente al bono | Dividir explotación por máximo reciente | W,c, probes, operadores, archivo | Mejora confirmada respecto a SW-UCB |
| I3 | Posible suma de beneficios | Activar guía sobre escalado online | Misma cadencia y presupuesto | Sin ventaja adicional; no adoptado |
| PH histórico | Memoria vieja ante cambios de recompensa | Detector de descenso + reinicio de UCB1 | Poblaciones y archivo | Sin superioridad corregida; cerrado |

En los tres brazos el hook cooperativo se llama sólo al realizar cruce. Desactivado devuelve el padre nativo y no consume RNG adicional. Se añadió limpieza de guía al reset. No se inyectan incumbentes ni se asigna al hijo el fitness del donante. Cada nuevo hijo pasa por la evaluación nativa.

Las instantáneas `baseline`, `research_v1`, `research_v2` y `confirmation_frozen` están en la campaña reciente. Existe una corrección append-only de procedencia: las primeras filas leyeron hashes de disco después de cargar módulos, por lo que esos hashes no identifican por sí solos el código ya cargado. La corrección conserva la fuente base y un ensayo previo de reproducción de cinco controles. En esta tarea se verifican archivos y métricas guardadas, sin repetir esas optimizaciones.

No se atribuye el resultado de I3 a “incompatibilidad genética demostrada”. El cambio de descendencia modifica recompensas y decisiones futuras; la interacción es una hipótesis y exige controles adicionales.

Fuentes: [procedencia base](../portfolio_loop_20261015/baseline_execution_provenance.json), [protocolo](../portfolio_loop_20261015/protocol.md), [recent_paired_statistics](tables/recent_paired_statistics.csv). Para parámetros y fórmulas, [catálogo](03_catalogo_algoritmos_portafolios.md).


## Línea paralela y estado externo

Existe además una línea P5/P6 de sensibilidad de c e inyección directa de incumbentes, distinta del padre externo. P7 seguía produciendo resultados durante la auditoría. Se documenta en [apéndice 32](32_linea_paralela_P5_P6_P7.md), con un corte parcial fijo, sin mezclar presupuestos ni incorporarlo como confirmación. El conteo de instancias corresponde al inicio: desapareció externamente `mojssp-dmab - copia`, mientras el repositorio original `mojssp-dmab` y este checkout conservaron su estado. Véase [preservación](00_preservacion_trazabilidad.md).
