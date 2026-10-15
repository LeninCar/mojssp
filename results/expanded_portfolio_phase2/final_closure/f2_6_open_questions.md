# Preguntas Abiertas e Hipótesis Pendientes para la Fase 3

Este documento formaliza las hipótesis teóricas, preguntas abiertas y directrices metodológicas derivadas de los hallazgos empíricos de la Fase 2, estructuradas como hoja de ruta para la investigación en la Fase 3 del proyecto:

**«Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)»**

---

## 1. Justificación y Formulación de la Hipótesis de Inyección de Soluciones

### A. Diagnóstico empírico de la Fase 2
En la Fase 2 se observó que el portafolio (tanto uniforme como adaptativo) obtiene un Hypervolume inferior al de los algoritmos individuales continuos en las 10 bases evaluadas ($p = 0.0020$). Al evaluar los hitos presupuestarios de $1\,000$ a $5\,000$ FE, la diferencia media frente a MOEA/D pasó de $-0.0342$ a $-0.0542$ en Hypervolume.

En las condiciones evaluadas:
- Una corrida continua de MOEA/D con $5\,000$ FE evoluciona su población de forma ininterrumpida a lo largo de todas las evaluaciones.
- En el portafolio de $5\,000$ FE, las evaluaciones se distribuyen entre los tres brazos (recibiendo cada algoritmo aproximadamente una tercera parte del presupuesto total), ejecutándose en bloques de 50 FE.
- Las soluciones halladas por cada brazo se consolidan en el Archivo Global Pareto pasivo, pero no se reintroducen en las poblaciones activas de los otros algoritmos.
- **Aclaración metodológica:** La hipótesis de que esta separación poblacional y la ausencia de migración constituyen el factor explicativo principal es una propuesta teórica fundada en la literatura de metaheurísticas de islas y búsqueda cooperativa, pero **no constituye un hecho demostrado empíricamente en la Fase 2**, dado que no se evaluó experimentalmente un esquema con transferencia.

### B. Formulación de la hipótesis de investigación (F3.1)
> **Hipótesis H1 (Inyección Elitista):** *«La inyección periódica de un subconjunto de soluciones no dominadas del Archivo Global Pareto en la población activa del brazo seleccionado al inicio de cada bloque reduce el aislamiento poblacional entre algoritmos, acelerando la convergencia local y permitiendo que el portafolio mejore su competitividad relativa frente a las ejecuciones individuales continuas.»*

### C. Preguntas experimentales asociadas para Fase 3:
1. **¿Qué proporción de la población debe reemplazarse?** (Tasa de reemplazo $\rho \in [0.05, 0.20]$).
2. **¿Qué criterio de selección de individuos salientes debe utilizarse?** (Individuos dominados en la población local, o individuos de menor distancia de apiñamiento).
3. **¿Cómo mitigar la pérdida prematura de diversidad genotípica?** (Riesgo de convergencia prematura cruzada).

---

## 2. Justificación y Formulación de la Hipótesis del Detector Page-Hinkley (PHT)

### A. Diagnóstico empírico de la Fase 2
En la Fase 2 se implementó **Sliding-Window UCB (SW-UCB)** sin detector de cambios. El análisis de las recompensas registradas reveló:
1. **Descenso en la frecuencia de mejoras:** En las etapas tardías de las trayectorias ($3\,000 - 5\,000$ FE), el $25.17\%$ de los bloques obtienen recompensa cero ($\Delta HV = 0$). Conforme el archivo global acumula soluciones de alta calidad, la obtención de mejoras en hipervolumen se vuelve menos frecuente.
2. **Distinción metodológica:** El descenso en la frecuencia de recompensas positivas es una propiedad observable de la serie temporal, pero **no equivale a una detección formal de cambios de régimen en la dinámica interna de los algoritmos**.
3. **Inercia de la ventana temporal fija ($W=10$):** SW-UCB descarta observaciones por antigüedad fija en la cola FIFO, con independencia de si el entorno experimenta una transición abrupta o un estancamiento prolongado.

### B. Formulación de la hipótesis de investigación (F3.2)
> **Hipótesis H2 (Detección de Deriva con Page-Hinkley):** *«La incorporación de un test secuencial de Page-Hinkley (PHT) sobre la serie temporal de recompensas de cada brazo permite contrastar formalmente la presencia de cambios de régimen (deriva en la tasa de mejora), habilitando mecanismos de reinicio selectivo o re-exploración forzada como alternativa al descarte por ventana estática ($W=10$).»*

### C. Advertencia metodológica para la tesis:
Page-Hinkley se plantea estrictamente como una hipótesis experimental. Su eficacia dependerá de una calibración cuidadosa de los parámetros de tolerancia $\delta$ y umbral $\lambda$, evitando disparos erráticos causados por la tasa basal de recompensas nulas.

---

## 3. Justificación y Formulación de la Hipótesis de Calibración de la Exploración ($c$)

### A. Diagnóstico empírico de la Fase 2
La reconstrucción exacta de las 2.910 decisiones adaptativas demostró que con $c = 0.07$:
- El término de exploración ($0.05978$) es en promedio **35.4 veces mayor** que el término de explotación ($0.00169$).
- La exploración invirtió la elección sugerida por la explotación en el **64.11%** de los bloques adaptativos.
- Las asignaciones acumuladas de evaluaciones se mantuvieron en una banda estrecha ($31.5\% - 35.5\%$), limitando la especialización adaptativa.

### B. Formulación de la hipótesis de investigación (F3.3)
> **Hipótesis H3 (Balance Escalar de UCB):** *«Ajustar el coeficiente de exploración $c$ al orden de magnitud típico de las mejoras observadas de Hypervolume ($c \in [0.005, 0.02]$) permite equilibrar los términos de explotación y exploración, incrementando la sensibilidad del selector hacia el brazo con mayor contribución marginal en cada etapa.»*

---

## 4. Justificación y Formulación de la Hipótesis de Recompensa Multiescala

### A. Diagnóstico empírico de la Fase 2
La recompensa actual depende exclusivamente de la mejora en el archivo global:
$$\text{reward} = \max(0, \Delta HV_{\text{global}})$$
Cuando un brazo realiza avances locales en su población pero ninguna de sus soluciones supera el umbral de dominancia del archivo global, recibe recompensa $0.0$, lo que conduce a una pérdida de información sobre el progreso relativo entre brazos en fases tardías.

### B. Formulación de la hipótesis de investigación (F3.4)
> **Hipótesis H4 (Recompensa Multiescala):** *«Una función de recompensa compuesta que incorpore una señal normalizada de progreso poblacional interno del brazo cuando $\Delta HV_{\text{global}} = 0$ provee retroalimentación informativa continua al selector, evitando la pérdida de gradiente en etapas avanzadas de la búsqueda.»*

---

## 5. Resumen de Prioridades Metodológicas para la Fase 3

| Prioridad | Componente | Tipo de Intervención | Objetivo Primario |
| :---: | :--- | :--- | :--- |
| **1** | **Inyección Elitista** | Transferencia de Soluciones | Evaluar experimentalmente si la migración de soluciones mitiga la desventaja frente a corridas continuas. |
| **2** | **Calibración de $c$** | Hiperparámetro UCB | Equilibrar el ratio exploración/explotación para permitir una diferenciación efectiva de asignaciones. |
| **3** | **Recompensa Multiescala** | Señal de Feedback | Mantener gradiente adaptativo en etapas donde la mejora del archivo global es infrecuente. |
| **4** | **Page-Hinkley (PHT)** | Detección de Cambios | Evaluar si la detección estadística de cambios de régimen supera el descarte pasivo por ventana fija. |
