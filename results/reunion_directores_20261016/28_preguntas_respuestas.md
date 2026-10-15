# 40 preguntas posibles y respuestas fundamentadas

## 1. ¿Por qué estos tres algoritmos?

Hecho: implementan tres mecanismos diferentes de selección: descomposición, ranking/crowding y fuerza/densidad. Interpretación: esa variedad hace razonable probar complementariedad. No garantiza que los tres deban mantenerse en el portafolio final.

Evidencia: [03_catalogo_algoritmos_portafolios.md](03_catalogo_algoritmos_portafolios.md).

## 2. ¿Qué aporta MOEA/D?

Hecho: mayor HV/AUC medio en confirmación y mayor MC histórico. Interpretación: es la referencia más fuerte de las evaluadas a estos presupuestos. No se ha demostrado superioridad universal.

Evidencia: [16_contribuciones_por_brazo.md](16_contribuciones_por_brazo.md).

## 3. ¿Qué aporta NSGA-II?

Hecho: existen victorias locales e históricas; su ventaja relativa aumenta con cuello de botella en ocho bases históricas. Interpretación: candidato para un ensayo dirigido, sin regla general confirmada tras multiplicidad.

Evidencia: [09_rendimiento_por_caracteristicas.md](09_rendimiento_por_caracteristicas.md).

## 4. ¿Qué aporta SPEA2?

Hecho: gana la base 5×5 reciente y aporta volumen exclusivo en otras uniones. Interpretación: su menor media no justifica eliminarlo sin ablación presupuestaria.

Evidencia: [14_complementariedad.md](14_complementariedad.md).

## 5. ¿Cómo funciona el portafolio?

Hecho: conserva tres estados, selecciona un brazo y ejecuta bloques de 50 FE, une archivos y actualiza crédito global. La selección no reinicia las poblaciones.

Evidencia: [02_arquitectura_portafolio.md](02_arquitectura_portafolio.md).

## 6. ¿Por qué se usa HV?

Hecho: mide el volumen dominado del frente aproximado respecto a una referencia fija. Interpretación: permite valorar conjuntos en los tres objetivos, pero depende de normalización/referencia y no describe toda la diversidad.

Evidencia: [03_catalogo_algoritmos_portafolios.md](03_catalogo_algoritmos_portafolios.md).

## 7. ¿Por qué AUC-HV?

Hecho: resume calidad durante las FE disponibles, no sólo al final. El informe integra por trapecios desde (0,0) y divide por B. Interpretación: ayuda a estudiar comportamiento anytime.

Evidencia: [12_analisis_estadistico.md](12_analisis_estadistico.md).

## 8. ¿Qué significa eficiencia?

Hecho operacional: calidad a igual FE, trayectoria, tiempo y probabilidad de alcanzar umbrales. Interpretación: no basta ser rápido si el conjunto de soluciones empeora.

Evidencia: [23_eficiencia.md](23_eficiencia.md).

## 9. ¿Qué significa adaptabilidad?

Hecho: asignación depende de recompensas recientes y cambia durante la corrida. Interpretación: su utilidad necesita comparación controlada; generalizar a nuevas familias requiere otra evidencia.

Evidencia: [24_adaptabilidad.md](24_adaptabilidad.md).

## 10. ¿Qué demuestra UCB escalado?

Hecho: cambiar sólo la escala de explotación mejora HV/AUC de SW-UCB en 8/8 bases de confirmación; HV Holm .015625. No demuestra optimalidad de c/W ni victoria sobre MOEA/D.

Evidencia: [17_analisis_adaptabilidad.md](17_analisis_adaptabilidad.md).

## 11. ¿Cómo se seleccionan brazos?

Hecho: probes, media de ventana y bono UCB; ausentes de ventana tienen infinito; empates sembrados. Escalado divide la media por un máximo común reciente.

Evidencia: [18_analisis_recompensas.md](18_analisis_recompensas.md).

## 12. ¿Qué demuestra la complementariedad?

Hecho: varios archivos aportan volumen que no cubren los otros. No demuestra beneficio a igual presupuesto ni especialización general por instancia.

Evidencia: [14_complementariedad.md](14_complementariedad.md).

## 13. ¿Qué significa contribución marginal?

Hecho: HV de unión menos HV de unión de los demás archivos completos. Hay que recuperar sustitutos antes dominados. No se suma como HV total.

Evidencia: [16_contribuciones_por_brazo.md](16_contribuciones_por_brazo.md).

## 14. ¿Por qué compartir soluciones?

Hipótesis: un genotipo ajeno puede aportar combinaciones que no alcanzó el receptor. Hecho: el replay produce señal positiva media con más diversidad, condicionada a esa asignación.

Evidencia: [20_analisis_cooperacion.md](20_analisis_cooperacion.md).

## 15. ¿Cómo se escoge el donante?

Hecho: extranjero, ausente del archivo local, más distante en objetivos normalizados por criterio maximin; se congela por bloque y sustituye segundo padre cada diez cruces elegibles.

Evidencia: [20_analisis_cooperacion.md](20_analisis_cooperacion.md).

## 16. ¿Se reutiliza gratis el fitness del hijo?

Hecho: no. Se comparte el genotipo padre y cada hijo se decodifica y evalúa nativamente, consumiendo FE. No equivale a insertar una solución evaluada en la población.

Evidencia: [04_cambios_implementados.md](04_cambios_implementados.md).

## 17. ¿Por qué no supera a MOEA/D?

Hecho: sigue una brecha de .019687 HV medio a 3000 FE. Hipótesis: fragmentación, profundidad, complementariedad insuficiente y crédito imperfecto. No hay un ensayo que identifique una causa única.

Evidencia: [22_por_que_no_supera_moead.md](22_por_que_no_supera_moead.md).

## 18. ¿Influye el tamaño?

Hecho: se observan diferencias y una excepción en 5×5. Interpretación: no puede separarse tamaño de perfil con una base por geometría reciente y una sola base mediana.

Evidencia: [08_rendimiento_por_tamano.md](08_rendimiento_por_tamano.md).

## 19. ¿Influyen los modos de velocidad?

Hecho: ofrecen intercambio tiempo–energía; los cinco modos están en todas las bases principales. No se puede estimar el efecto del número de modos sin variarlo en corridas comparables.

Evidencia: [06_caracterizacion_instancias.md](06_caracterizacion_instancias.md).

## 20. ¿Cómo se controla FE?

Hecho: inicialización y cada evaluación de hijo consumen presupuesto; los 312 registros suman 3000 FE reales y 60 bloques. Las métricas offline no generan soluciones nuevas.

Evidencia: [30_auditoria_final.md](30_auditoria_final.md).

## 21. ¿Qué validez tienen los resultados?

Hecho: controles internos, fuente reciente congelada, base como unidad, semillas comunes, archivos y recálculos. Límite: pocas bases, generador único, perfiles confundidos y test sin abrir.

Evidencia: [12_analisis_estadistico.md](12_analisis_estadistico.md).

## 22. ¿Qué falta experimentar?

Recomendación: ablación de presupuesto/brazos y contraste dirigido de cuello de botella; luego cooperación autónoma si se prioriza. Requiere acuerdo de objetivo, efecto mínimo y protocolo de validación.

Evidencia: [29_decisiones_directores.md](29_decisiones_directores.md).

## 23. ¿Cuál es el aporte científico?

Interpretación apoyada: diagnóstico del crédito, ablación aislada de escala, cooperación controlada, MC correcto y resultados negativos trazables. La tesis no depende de inventar superioridad del portafolio.

Evidencia: [25_relacion_objetivos_tesis.md](25_relacion_objetivos_tesis.md).

## 24. ¿Page-Hinkley funcionó?

Hecho: C5 no acreditó ventaja corregida; media 165 FE de resondeo. La comparación reutiliza sus corridas de calibración y no es confirmación independiente. No probar ventaja no prueba equivalencia.

Evidencia: [01_evolucion_investigacion.md](01_evolucion_investigacion.md).

## 25. ¿Qué significa un HV mayor que uno?

Hecho: referencia 1.1 en tres dimensiones permite hasta 1.331 en la caja ideal normalizada. HV >1 es compatible con la definición; no es un porcentaje de óptimo.

Evidencia: [03_catalogo_algoritmos_portafolios.md](03_catalogo_algoritmos_portafolios.md).

## 26. ¿Son 450 experimentos independientes?

Hecho: son cortes de 150 trayectorias históricas. Además, 1000/3000/5000 comparten historia, y las semillas repiten una misma base.

Evidencia: [12_analisis_estadistico.md](12_analisis_estadistico.md).

## 27. ¿Cuántas instancias hay realmente?

Hecho: 2746 copias .dzn, 1336 contenidos distintos; el conjunto expandido tiene 200 variantes de 40 bases. El inventario incluye inválidos y archivos sin resultados comparables.

Evidencia: [06_caracterizacion_instancias.md](06_caracterizacion_instancias.md).

## 28. ¿Se utilizó el test final?

Hecho: no se analizó rendimiento reservado ni se abrieron sus instancias para características detalladas. Sólo se conservaron hashes y metadatos declarados de 80 variantes/16 bases. Confirmación reciente es interna.

Evidencia: [30_auditoria_final.md](30_auditoria_final.md).

## 29. ¿Compartir archivo es cooperación?

Hecho: una salida Pareto compartida puede ser unión pasiva; usarla para recompensa comunica crédito al selector. Sólo la guía transmite genotipos a variación. Son mecanismos diferentes.

Evidencia: [02_arquitectura_portafolio.md](02_arquitectura_portafolio.md).

## 30. ¿Por qué más diversidad no implica más HV?

Hecho: distancia genética, rango y volumen exclusivo son métricas diferentes. Hipótesis: hijos distantes pueden no converger o aportar regiones pequeñas/redundantes. No se registró su destino completo.

Evidencia: [15_espacio_objetivos.md](15_espacio_objetivos.md).

## 31. ¿Por qué no funcionó la combinación?

Hecho: ΔHV medio negativo con IC que incluye cero, 3/6 bases favorables; no se adoptó. Hipótesis: interacción de descendencia y crédito/asignación. No está causalmente identificada.

Evidencia: [21_analisis_combinacion_mecanismos.md](21_analisis_combinacion_mecanismos.md).

## 32. ¿La mejora de guía es estadísticamente segura?

Hecho: HV Holm .054688, IC bootstrap positivo y 7/8 bases favorables. Interpretación: señal condicional prometedora, no confirmación fuerte al 5%; no seleccionar sólo el resultado más favorable.

Evidencia: [12_analisis_estadistico.md](12_analisis_estadistico.md).

## 33. ¿La guía cuesta 3000 o 6000 FE?

Hecho: tratamiento 3000; control para obtener traza específica otras 3000. El par completo cuesta 6000 desde cero. No penalizar dos veces si la traza ya existe, pero declararla.

Evidencia: [13_eficiencia_computacional.md](13_eficiencia_computacional.md).

## 34. ¿Eliminarías NSGA-II o SPEA2?

Recomendación provisional: no por una media agregada. Medir ablaciones 2/3 brazos a igual B y múltiples bases. MC final no es efecto de reasignar FE tras eliminar un brazo.

Evidencia: [29_decisiones_directores.md](29_decisiones_directores.md).

## 35. ¿Una recompensa cero indica estancamiento definitivo?

Hecho: indica ausencia de ganancia global en ese bloque. Hubo recuperaciones después de ceros y el estado local puede mejorar sin superar el archivo global.

Evidencia: [19_asignacion_presupuesto.md](19_asignacion_presupuesto.md).

## 36. ¿Las correlaciones permiten configurar el portafolio?

Hecho: son exploratorias y con n pequeño; tamaño/perfil están confundidos. Interpretación: sirven para diseñar hipótesis, no para un modelo de selección generalizado.

Evidencia: [09_rendimiento_por_caracteristicas.md](09_rendimiento_por_caracteristicas.md).

## 37. ¿Qué cambió durante esta auditoría?

Hecho: sólo se crearon scripts, tablas, figuras y documentos en el directorio de reunión. No se cambiaron algoritmos, resultados históricos, ramas ni se hicieron push. Se contrastan hashes antes/después.

Evidencia: [30_auditoria_final.md](30_auditoria_final.md).

## 38. ¿Conocemos el Pareto óptimo?

Hecho: no. Los archivos son aproximaciones observadas y las cotas son analíticas conservadoras. No se interpreta HV como porcentaje de óptimo conocido.

Evidencia: [15_espacio_objetivos.md](15_espacio_objetivos.md).

## 39. ¿Es causal el efecto de los perfiles?

Hecho: las variantes históricas comparten base y permiten un contraste emparejado de la perturbación del generador. Límite: cambian instancia y normalización; no prueba un efecto universal del rasgo ni una causa de superioridad.

Evidencia: [09_rendimiento_por_caracteristicas.md](09_rendimiento_por_caracteristicas.md).

## 40. ¿Qué se puede defender mañana?

Interpretación basada en evidencia: corrección reproducible del selector, complementariedad limitada y cooperación condicional, con una agenda concreta. La reunión debe acordar el siguiente contraste y el alcance final.

Evidencia: [26_resumen_ejecutivo.md](26_resumen_ejecutivo.md).
