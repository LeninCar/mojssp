# Resumen ejecutivo para reunión del 16 de octubre

**Estado:** portafolio MO-JSSP implementado y evaluado; mejora interna reproducible del selector; superioridad sobre el mejor individual y generalización todavía no demostradas. Este es material de seguimiento, no una sustentación final. Extensión objetivo: tres páginas de lectura, sin figuras insertadas.

## Qué hay construido

MOEA/D, NSGA-II y SPEA2 comparten representación y evaluación de Cmax, tardanza y energía. El orquestador conserva estados y reparte bloques de FE. Se compararon uniforme, SW-UCB original, UCB1/PH, UCB escalado, padre externo con replay y combinación. El archivo global agrega soluciones y mide crédito; sólo las variantes de padre externo transfieren genotipos.

## Diez hallazgos

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

## Resultado principal comparable

| Método | HV | AUC-HV | Tiempo (s) |
| --- | --- | --- | --- |
| SW-UCB original | 0.9107 | 0.8638 | 10.6694 |
| Padre externo con replay | 0.9192 | 0.8717 | 11.1594 |
| MOEA/D | 0.9511 | 0.8925 | 10.3429 |
| NSGA-II | 0.9362 | 0.8872 | 11.0933 |
| UCB escalado | 0.9314 | 0.8784 | 10.8257 |
| SPEA2 | 0.9316 | 0.8873 | 10.6582 |
| Uniforme | 0.9077 | 0.8622 | 10.7238 |


Ocho bases nuevas, tres semillas, 3000 FE. El tiempo de guía excluye obtener la traza control de 3000 FE adicional. Escalado cambia el reparto MOEA/D/NSGA-II/SPEA2 de 34.44/32.71/32.85% a 40.83/25.83/33.33%; tiempo medio +1.46%, diversidad genética +11.56%. No equivale a ganar al mejor individual.

## Validez y límites

Inferencia por base, semillas promediadas, bootstrap y pruebas exactas, familia principal de dos candidatos con Holm. La confirmación es del mismo generador y repite perfil asociado a tamaño. Los 450 cortes históricos son 150 trayectorias, y el piloto coincide en calidad con el primer corte. Los datos originales y algoritmos se preservan; esta auditoría no consumió FE de optimización. La recomputación de 312 HV/AUC/MC coincide a precisión numérica.

## Qué proponer a los directores

Conservar escalado como candidato, fijar eficiencia respecto al portafolio original y mantener MOEA/D como referencia. Acordar una ablación presupuestaria para H1/H2 y una hipótesis dirigida de cuello de botella, con bases independientes. Decidir si la cooperación debe demostrarse como política online o permanecer como ensayo de mecanismo. Definir familias de pruebas, mínimo efecto útil y condición de apertura del test final antes de nuevas corridas. No afinar con el holdout.

Lectura de apoyo: [guion](27_guion_reunion.md), [decisiones](29_decisiones_directores.md), [informe integral](INFORME_INTEGRAL_MOJSSP.md), [auditoría](30_auditoria_final.md).


## Línea paralela y estado externo

Existe además una línea P5/P6 de sensibilidad de c e inyección directa de incumbentes, distinta del padre externo. P7 seguía produciendo resultados durante la auditoría. Se documenta en [apéndice 32](32_linea_paralela_P5_P6_P7.md), con un corte parcial fijo, sin mezclar presupuestos ni incorporarlo como confirmación. El conteo de instancias corresponde al inicio: desapareció externamente `mojssp-dmab - copia`, mientras el repositorio original `mojssp-dmab` y este checkout conservaron su estado. Véase [preservación](00_preservacion_trazabilidad.md).
