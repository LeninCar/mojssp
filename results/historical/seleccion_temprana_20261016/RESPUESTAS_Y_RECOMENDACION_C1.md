# Respuestas antes del piloto C1

**1. ¿Hay evidencia de que el rendimiento inicial identifica al mejor final?** Hay información observable y heterogeneidad, pero no una ventaja fiable de los criterios ensayados frente a siempre MOEA/D. En desarrollo reciente, máximo HV a200 por brazo acierta6/18 (33.3%), frente a13/18 (72.2%) del baseline. Son6 bases con3 semillas, no18 bases. Regret .016560 frente a .005434. La diferencia por base es exploratoria y no se presenta como confirmación nueva.

**2. ¿Qué pruebas son evaluables?** Se recuperan100/200/300/500/1000/3000 por brazo en loop; esos cortes hasta5000 en Fase 2, y sólo hasta1000 en P7/piloto. No hay trayectorias tempranas de Fase 1 ni benchmark. Para B3000, cortes100,200,300,500 permiten continuación;1000 agota presupuesto y3000 lo supera. Para B1000 sólo100,200,300 son coste-factibles entre los cortes solicitados. Siempre MOEA/D no paga prueba.

**3. ¿El ganador inicial puede terminar peor?** Sí. En desarrollo, A200 termina estrictamente peor en6/18 pares. Las filas con los tres HV, fuentes y márgenes se conservan, junto con todos los casos favorables y desfavorables. No se suman esos errores a través de múltiples cortes para fingir observaciones independientes.

**4. ¿Qué falta?** Archivos y estados en el punto exacto de continuación, geometría de la unión final, tiempo y contabilidad real de una política de prueba+continuación. No se pueden obtener de medias ni de tres HV individuales. También faltan bases nuevas para generalizar y un margen práctico acordado antes de una prueba confirmatoria.

**5. ¿Se puede estimar acierto sin nuevas FE?** Sí: se evaluaron seis definiciones, con A=B0 por construcción y C100=A. Las decisiones usan sólo checkpoints hasta el corte; el HV final se consulta después para puntuarlas. Los criterios D y las sensibilidades de empate usan parámetros fijos descriptivos, no umbrales optimizados. Los IC remuestrean bases tras promediar semillas/perfiles.

**6. ¿Qué requiere el piloto real?** Verificar estado/RNG, FE exactas, presupuesto restante y unión de todos los archivos retenidos durante la continuación; medir AUC, calidad y tiempo efectivos frente a MOEA/D/uniforme/escalado. El HV local del elegido en2600 puede consultarse retrospectivamente, pero no reemplaza ese resultado global ni implementa la política. No hubo simulación de búsqueda nueva.

**7. ¿Mantener200 o cambiarlo?** Los resultados de desarrollo justifican revisar la expectativa de eficacia de elegir por HV200; no justifican recomendar un corte alternativo validado. A100 acierta55.6%, A30033.3%, A50027.8%; no hay mejora monotónica ni ventaja sobre72.2% del baseline. D100 tiene una mejora de regret minúscula e incierta frente a MOEA/D, no suficiente para seleccionarlo después de explorar muchos cortes. No se usa confirmación para elegir1000 ni P7 para transferir500 a otro presupuesto.

**Recomendación:** detenerse para revisión. Si se conserva C1, presentarlo como piloto técnico/de falsificación con200 por brazo y comparadores fuertes, no como mecanismo ya respaldado; alternativamente, posponerlo hasta acordar una hipótesis de señal más concreta. No se ha ejecutado ni implementado C1 y no se propone un selector definitivo.

Lectura y evidencia: [informe completo](INFORME_SELECCION_TEMPRANA.md), [matriz con procedencia](tables/v2/accuracy_regret_matrix_with_provenance.csv), [datos faltantes](tables/v2/missing_data_inventory.csv), [verificación](AUDITORIA_FINAL.md).
