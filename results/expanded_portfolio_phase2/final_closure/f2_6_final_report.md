# Informe Científico Consolidado de la Fase 2

**Proyecto de Tesis:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Fase:** F2.6 — Consolidación científica, reproducibilidad y cierre formal de la Fase 2  
**Fecha:** Octubre 2026  
**Autor:** Auditoría Técnica y Científica del Proyecto  

---

## 1. Resumen Ejecutivo y Pregunta de Investigación

La investigación aborda la pregunta central de tesis:

> **¿Cómo puede implementarse un portafolio de algoritmos orientado a la resolución del Multi-Objective Job Shop Scheduling Problem (MO-JSSP) de manera eficiente y adaptable a diferentes criterios de optimización?**

La Fase 2 tuvo como objetivo diseñar, integrar, validar experimentalmente y auditar un **portafolio adaptativo de tres brazos fijos** compuesto por las metaheurísticas multiobjetivo seleccionadas a partir de la Fase 1:
1. **MOEA/D** (Multi-Objective Evolutionary Algorithm based on Decomposition).
2. **NSGA-II** (Non-dominated Sorting Genetic Algorithm II).
3. **SPEA2** (Strength Pareto Evolutionary Algorithm 2).

Se evaluaron dos políticas de asignación de bloques computacionales:
- **Asignación Uniforme:** Selector determinista cíclico Round-Robin.
- **Asignación Adaptativa:** Selector Sliding-Window Upper Confidence Bound (SW-UCB) con tamaño de ventana $W = 10$ y coeficiente de exploración $c = 0.07$, gobernado por la mejora marginal en el Hypervolume global ($\text{reward} = \max(0, \Delta HV_{\text{global}})$).

La campaña experimental evaluó **ocho configuraciones dimensionales** y **diez instancias base de desarrollo** bajo tres semillas maestras y cinco métodos, ejecutando **150 trayectorias continuas** con seguimiento en los hitos presupuestarios de 1.000, 3.000 y 5.000 Evaluaciones de la Función Objetivo (FE), generando **450 registros de hitos presupuestarios** en total.

---

## 2. Respuestas a las Preguntas Científicas Fundamentales

### P1. ¿La implementación respeta los presupuestos FE y es reproducible?
- **Evidencia:** 10 de 10 verificaciones de integridad superadas exitosamente. En las 150 trayectorias continuas y sus 450 registros de hitos presupuestarios no se registró ninguna evaluación de sobrecoste ($\text{overshoot} = 0$, $\text{evaluations\_used} \equiv \text{budget}$). Se verificaron 15.000 checkpoints sin violaciones a la monotonía débil del Hypervolume acumulado. La coherencia entre el piloto F2.4 y el diagnóstico F2.5.1 a 1.000 FE fue absoluta ($\Delta HV = 0.0$, diferencia de tamaño de archivo = 0). Las 2.910 decisiones adaptativas de SW-UCB fueron reproducidas al 100% bit a bit. La suite completa de 375 pruebas unitarias e integrales pasó sin errores en 15.74 segundos.
- **Conclusión:** **SÍ.** La implementación respeta rigurosamente los presupuestos computacionales y es 100% reproducible.

### P2. ¿SW-UCB supera a Round-Robin en las instancias de desarrollo evaluadas?
- **Evidencia:**
  - A 1.000 FE: $\bar{D} = -0.0007$ ($p = 0.7695$, Wilcoxon pareado sobre $N=10$ bases; sin diferencia estadísticamente significativa detectada).
  - A 3.000 FE: $\bar{D} = +0.0054$ ($p = 0.0020$, estadísticamente significativo bajo Holm-Bonferroni, $d = +1.17$, 10 victorias por base de 10).
  - A 5.000 FE: $\bar{D} = +0.0033$ ($p = 0.0098$, estadísticamente significativo bajo Holm-Bonferroni, $d = +0.94$, 9 victorias por base de 10).
- **Conclusión:** **SÍ, en los hitos de 3.000 y 5.000 FE.** La política adaptativa SW-UCB supera a la asignación uniforme con significancia estadística en las diez bases, con una ventaja de magnitud práctica moderada ($\Delta HV \approx 0.003 - 0.005$). En el hito de 1.000 FE no se detectó diferencia estadísticamente significativa entre ambas políticas.

### P3. ¿La ventaja depende del presupuesto?
- **Evidencia:** En el hito de 1.000 FE (20 bloques de 50 FE), 6 bloques corresponden al arranque forzado (warm-up y sondeo inicial), dejando únicamente 14 bloques adaptativos, lo que resulta insuficiente para manifestar aprendizaje en el selector. En 3.000 FE (60 bloques) la diferencia observada es mayor ($\bar{D} = +0.0054$), mientras que en 5.000 FE (100 bloques) la diferencia observada es de $\bar{D} = +0.0033$. En las etapas tardías ($3.000 - 5.000$ FE), el $25.17\%$ de los bloques reciben recompensa cero ($\Delta HV = 0$), reduciendo la frecuencia de mejoras.
- **Conclusión:** **SÍ.** La ventaja de la política adaptativa requiere una cantidad mínima de bloques adaptativos para manifestarse ($\ge 3.000$ FE) y muestra variaciones en su magnitud entre los hitos discretos evaluados. No debe presentarse 3.000 FE como un presupuesto óptimo global ni asumirse una estabilización definitiva sin evaluar presupuestos mayores.

### P4. ¿El portafolio supera a alguno de los tres algoritmos individuales?
- **Evidencia:** En los tres hitos de presupuesto (1k, 3k y 5k FE), tanto el portafolio adaptativo como el uniforme obtuvieron un Hypervolume inferior al de MOEA/D, NSGA-II y SPEA2 continuos en las 10 bases evaluadas ($p \le 0.0137$, significativo tras corrección FDR de Benjamini-Hochberg). A 5.000 FE, la diferencia media frente a MOEA/D es de $-0.0542$ y frente al Virtual Best Solver (VBS) es de $-0.0583$.
- **Conclusión:** **NO.** El portafolio en su configuración actual (archivo global pasivo, sin inyección de soluciones) no supera a ninguno de los tres algoritmos individuales continuos en las condiciones analizadas.

### P5. ¿Los tres brazos aportan soluciones complementarias?
- **Evidencia:** El análisis de la unión no dominada de las soluciones standalone (a 5.000 FE) demostró que:
  - MOEA/D aporta $41.9$ soluciones exclusivas ($47.3\%$ del frente conjunto).
  - NSGA-II aporta $18.2$ soluciones exclusivas ($20.6\%$).
  - SPEA2 aporta $28.5$ soluciones exclusivas ($32.2\%$).
  - Las soluciones compartidas idénticas representan el $0.0\%$.
  - La reducción de Hypervolume al retirar cualquiera de los algoritmos es de $+0.0883$ para MOEA/D, $+0.0053$ para NSGA-II y $+0.0102$ para SPEA2.
- **Conclusión:** **SÍ.** Los tres algoritmos exploran regiones diferenciadas del espacio objetivo en ejecuciones independientes.

### P6. ¿El selector diferencia suficientemente el esfuerzo entre brazos?
- **Evidencia:** A 5.000 FE, el reparto de esfuerzo fue: MOEA/D $34.93\%$, NSGA-II $32.70\%$, SPEA2 $32.37\%$. La reconstrucción exacta del índice UCB demostró que el término de exploración ($0.05978$) fue **35.4 veces superior** al término de explotación ($0.00169$). La exploración revirtió la decisión de explotación en el **64.11%** de los bloques adaptativos.
- **Conclusión:** **NO.** Con $c = 0.07$ y mejoras $\Delta HV \approx O(10^{-3})$, el selector está fuertemente dominado por el bonus de exploración, lo que mantiene la distribución de asignaciones en una banda estrecha ($31.5\% - 35.5\%$).

### P7. ¿Qué limitaciones arquitectónicas están demostradas y cuáles son hipótesis?
- **Demostradas empíricamente:**
  1. El portafolio pasivo obtiene menor HV que los algoritmos continuos individuales bajo los presupuestos evaluados.
  2. Incrementar el presupuesto de 1.000 a 5.000 FE no redujo la diferencia frente a los algoritmos continuos.
  3. El parámetro $c=0.07$ impone un término de exploración que supera ampliamente al de explotación, restringiendo la diferenciación de brazos.
  4. La frecuencia de bloques sin recompensa aumenta a lo largo de la trayectoria (alcanzando $25\%$ en etapas tardías).
- **Hipótesis teóricas (no demostradas en la Fase 2):**
  1. Que la inyección de soluciones del archivo global a las poblaciones locales mitigará la desventaja frente a las corridas continuas.
  2. Que la incorporación de un detector Page-Hinkley mejorará la velocidad de respuesta adaptativa ante cambios en la tasa de mejora.

### P8. ¿Qué resultados justifican investigar Page-Hinkley?
- **Evidencia justificativa:** El descenso observable en la frecuencia de recompensas positivas ($10.95\%$ de bloques sin mejora en bloques 6–20 $\rightarrow$ $25.17\%$ en bloques 61–100) y la rigidez de la ventana fija ($W=10$) ante estancamientos prolongados.
- **Conclusión:** Justifica investigar como hipótesis experimental si un test estadístico secuencial de cambios de régimen permite gestionar la memoria de los brazos con mayor adaptabilidad que una ventana estática.

### P9. ¿Qué resultados justifican investigar inyección de soluciones?
- **Evidencia justificativa:** Los tres brazos producen soluciones complementarias en ejecuciones individuales, pero en el portafolio cada algoritmo opera de forma aislada con una fracción del presupuesto total.
- **Conclusión:** Justifica formular como hipótesis prioritaria de la Fase 3 que la transferencia periódica de soluciones élite desde el archivo global hacia las poblaciones locales permitirá transferir avances entre algoritmos.

---

## 3. Síntesis de Resultados en los Hitos Presupuestarios

Resultados agregados por método en los tres hitos presupuestarios (150 trayectorias continuas evaluadas en 10 bases):

| Presupuesto | Método | Hypervolume Medio | Desv. Est. | Diferencia vs. MOEA/D | Diferencia vs. VBS |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **1.000 FE** | MOEA/D | $0.929894$ | $0.0763$ | Base de comp. | $-0.0070$ |
| | NSGA-II | $0.922717$ | $0.0811$ | $-0.0072$ | $-0.0142$ |
| | SPEA2 | $0.919666$ | $0.0792$ | $-0.0102$ | $-0.0172$ |
| | Uniforme | $0.896374$ | $0.0837$ | $-0.0335$ | $-0.0405$ |
| | DMAB | $0.895674$ | $0.0841$ | $-0.0342$ | $-0.0412$ |
| **3.000 FE** | MOEA/D | $1.001600$ | $0.0741$ | Base de comp. | $-0.0055$ |
| | NSGA-II | $0.984428$ | $0.0769$ | $-0.0172$ | $-0.0227$ |
| | SPEA2 | $0.977305$ | $0.0765$ | $-0.0243$ | $-0.0298$ |
| | Uniforme | $0.948995$ | $0.0772$ | $-0.0526$ | $-0.0581$ |
| | DMAB | $0.954422$ | $0.0768$ | $-0.0472$ | $-0.0527$ |
| **5.000 FE** | MOEA/D | $1.038038$ | $0.0718$ | Base de comp. | $-0.0041$ |
| | NSGA-II | $1.014046$ | $0.0754$ | $-0.0240$ | $-0.0281$ |
| | SPEA2 | $1.003373$ | $0.0743$ | $-0.0347$ | $-0.0388$ |
| | Uniforme | $0.980555$ | $0.0761$ | $-0.0575$ | $-0.0616$ |
| | DMAB | $0.983806$ | $0.0759$ | $-0.0542$ | $-0.0583$ |

---

## 4. Amenazas a la Validez y Limitaciones

1. **Validez Interna:**
   - *Escalamiento UCB:* El coeficiente $c=0.07$ no fue optimizado empíricamente sobre el problema, lo que generó un término de exploración desproporcionado respecto a las recompensas $\Delta HV$.
   - *Señal de recompensa:* La función $\max(0, \Delta HV)$ asigna valor nulo a bloques que logran mejoras poblacionales internas si estas no logran ingresar al archivo global.
2. **Validez Externa:**
   - *Representatividad de instancias:* La evaluación se condujo sobre 10 instancias base de desarrollo pertenecientes a 8 configuraciones dimensionales ($5\times 5$ a $50\times 50$). El comportamiento en instancias no vistas se evaluará en el conjunto de prueba holdout al concluir la investigación.
   - *Granularidad de bloque:* Se empleó un bloque fijo de 50 FE. No se exploró la sensibilidad a bloques de mayor tamaño.

---

## 5. Directrices para el Documento de Tesis

1. **Transparencia en el desempeño comparativo:** Reportar explícitamente que el portafolio pasivo multi-algoritmo sin migración obtiene menor Hypervolume que los algoritmos continuos bajo las condiciones evaluadas.
2. **Estructura estadística jerárquica:** Reportar la inferencia estadística sobre las 10 instancias base independientes ($df = 9$), utilizando intervalos de confianza $t$ y pruebas pareadas de Wilcoxon con corrección de Holm-Bonferroni.
3. **Distinción entre evidencia e hipótesis:** Enmarcar la inyección de soluciones y el detector Page-Hinkley como hipótesis de investigación formuladas a partir de las limitaciones diagnosticadas en la Fase 2, no como conclusiones demostradas.
