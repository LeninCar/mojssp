# Dictamen de Cierre Metodológico de la Fase 2

**Dictamen Oficial del Auditor:** **APTO CON OBSERVACIONES**

La Fase 2 del proyecto «Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)» ha cumplido con los objetivos técnicos y de diseño experimental establecidos en la arquitectura. La integración de los tres brazos fijos (MOEA/D, NSGA-II, SPEA2) es computacionalmente sólida, exacta en presupuesto y reproducible.

Sin embargo, el cierre metodológico se otorga con **observaciones formales** que deben guiar la formulación de la Fase 3 y evitar afirmaciones no respaldadas en el documento de tesis.

---

### 1. Hallazgos Críticos
1. **La fragmentación del presupuesto sin inyección es la limitación central:** El portafolio pierde frente a los algoritmos continuos porque divide las evaluaciones entre tres poblaciones estancas. El aumento de presupuesto a $5\,000$ FE no cierra la brecha, sino que la amplía ligeramente.
2. **Desequilibrio del factor de exploración UCB:** Con $c = 0.07$, el término de exploración es $pprox 35$ veces superior al término de explotación, lo que restringe la diferenciación entre brazos a una banda estrecha ($31.5\% - 35.5\%$).
3. **Decaimiento asintótico de la recompensa:** Más del $25\%$ de los bloques en fases tardías ($3\,000 - 5\,000$ FE) obtienen recompensa cero, lo que degrada la señal de gradiente del selector.

---

### 2. Hallazgos Menores
1. **Diferenciación positiva confirmada a partir de 3.000 FE:** DMAB supera a la asignación uniforme a $3\,000$ FE ($p = 0.0020$) y $5\,000$ FE ($p = 0.0098$) sobre las 10 bases independientes.
2. **Defensa del parámetro `max_generations=None`:** Se determinó que la modificación de `max_generations=None` en NSGA-II constituyó una corrección de interoperabilidad técnica indispensable para permitir presupuestos $> 1\,500$ FE, con impacto cero en los resultados de $1\,000$ FE.

---

### 3. Correcciones Obligatorias para el Documento de Tesis
1. **No afirmar superioridad del portafolio sobre algoritmos individuales:** El portafolio actual (pasivo, sin inyección) no supera a MOEA/D, NSGA-II ni SPEA2 continuos. Esta honestidad científica debe quedar explícita en los resultados.
2. **Reportar agregación por base:** En el análisis inferencial, no reportar las 30 corridas como 30 muestras independientes; reportar la agregación sobre las 10 bases independientes con intervalos de confianza t de Student ($df=9$) o pruebas no paramétricas pareadas.
3. **Presentar la inyección como propuesta de mejora (Fase 3), no como hecho demostrado:** No afirmar que la falta de inyección "causa un coste irrecuperable" sin presentarla como una hipótesis fundada teóricamente pendiente de evaluación experimental.

---

### 4. Recomendaciones Prioritarias para la Siguiente Fase
1. **F3.1: Inyección Elitista Periódica:** Introducir migración de soluciones élite del Archivo Global Pareto a la población del brazo seleccionado antes de su bloque de ejecución.
2. **F3.2: Recompensa Normalizada o Multiescala:** Reformular el cálculo de recompensa para incorporar progreso poblacional local cuando $\Delta HV = 0$, y calibrar el parámetro $c \in [0.01, 0.03]$ para equilibrar la exploración y explotación.
