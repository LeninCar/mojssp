# Revisión Crítica de las Afirmaciones Metodológicas de F2.5.1

Auditoría científica independiente sobre las siete afirmaciones formuladas en el informe F2.5.1, evaluando su correspondencia con la evidencia experimental y proponiendo redacciones científicamente defendibles.

---

### Afirmación 1: «DMAB supera a uniforme de forma concluyente»
- **Dictamen:** **PARCIALMENTE RESPALDADA.**
- **Evidencia experimental:**
  - A $1\,000$ FE: DMAB **no** supera a uniforme ($ar{D} = -0.0007$, $p = 0.7695$ sobre las 10 bases; 7 victorias, 0 empates, 3 derrotas a nivel base; 12/11/7 a nivel de corrida). El IC 95% $[-0.0041, +0.0027]$ incluye el cero.
  - A $3\,000$ FE: DMAB sí supera a uniforme con significancia estadística ($ar{D} = +0.0054$, $p = 0.0020$, $d = +1.17$, 10/0/0 victorias por base).
  - A $5\,000$ FE: La ventaja se mantiene ($ar{D} = +0.0033$, $p = 0.0098$, $d = +0.94$, 9/0/1 victorias por base).
  - Calificar la ventaja como "concluyente" es excesivo: a $1\,000$ FE es inexistente, y en $3\,000$ y $5\,000$ FE su magnitud práctica es modesta ($\Delta HV pprox 0.003 - 0.005$).
- **Redacción defendible:** *«A presupuestos de 3.000 y 5.000 FE, el selector DMAB supera a la asignación uniforme de manera estadísticamente significativa en las 10 bases evaluadas, con una ventaja de magnitud moderada. A 1.000 FE, ambas políticas son estadísticamente indistinguibles.»*

---

### Afirmación 2: «El presupuesto es la causa de la inferioridad»
- **Dictamen:** **INCORRECTA.**
- **Evidencia experimental:**
  - Si la inferioridad del portafolio frente a los algoritmos individuales fuera causada por un presupuesto insuficiente, quintuplicar el presupuesto de $1\,000$ a $5\,000$ FE habría reducido la brecha.
  - Los datos demuestran lo contrario: la brecha media frente a MOEA/D se amplió de $-0.0342$ a $-0.0542$, y frente al VBS de $-0.0412$ a $-0.0583$.
  - La causa real es la fragmentación del presupuesto entre tres poblaciones estancas que evolucionan $pprox 1/3$ de las generaciones que una corrida continua, no la escasez absoluta de presupuesto.
- **Redacción defendible:** *«El aumento de presupuesto no redujo la desventaja del portafolio frente a los algoritmos individuales continuos. La inferioridad observada proviene de la fragmentación del presupuesto entre algoritmos aislados, lo que priva a cada brazo de la profundidad evolutiva que alcanza una corrida individual continua.»*

---

### Afirmación 3: «La ausencia de inyección impone un coste irrecuperable»
- **Dictamen:** **NO DEMOSTRADA (como afirmación factual) / RESPALDADA (como hipótesis teórica).**
- **Evidencia experimental:**
  - En la Fase 2 **nunca se implementó ni se evaluó una variante con inyección de soluciones**.
  - Aunque es un principio bien fundamentado en metaheurísticas híbridas y algoritmos de islas, calificar empíricamente el coste como "irrecuperable" sin contrastar un tratamiento control (con inyección) frente a uno sin inyección constituye una extrapolación no probada.
- **Redacción defendible:** *«Se formula como hipótesis teórica prioritaria que la falta de inyección de soluciones entre brazos impide transferir el conocimiento acumulado en el archivo global, dejando a cada algoritmo evolucionando en aislamiento.»*

---

### Afirmación 4: «SW-UCB funciona correctamente porque asigna más FE a MOEA/D»
- **Dictamen:** **PARCIALMENTE RESPALDADA.**
- **Evidencia experimental:**
  - MOEA/D recibe la mayor asignación promedio ($34.9\% - 35.4\%$).
  - Sin embargo, la auditoría del índice UCB demostró que el término de exploración ($0.0598$) es en promedio **35.4 veces mayor** que el término de explotación ($0.0017$).
  - La asignación permanece confinada en un rango muy estrecho ($31.5\% - 35.5\%$) debido a que el parámetro $c = 0.07$ domina la decisión cuando las recompensas $\Delta HV$ son del orden de $10^{-3}$ o cero.
- **Redacción defendible:** *«SW-UCB favorece de forma consistente al algoritmo con mayor contribución marginal (MOEA/D), pero la diferenciación es modesta debido a que el término de exploración relativo a la magnitud de las recompensas mantiene una alta tasa de rotación entre los tres brazos.»*

---

### Afirmación 5: «El selector tiene un sobrecoste inferior al 1.8%»
- **Dictamen:** **RESPALDADA.**
- **Evidencia experimental:**
  - La auditoría temporal confirma que la orquestación, gestión de ventana y cálculo de $\Delta HV$ consumieron $pprox 39.5$ segundos de los $2\,245$ segundos totales de pared (exactamente $1.76\%$). Más del $98\%$ del tiempo de cómputo corresponde a la decodificación y evaluación de schedules.
- **Redacción defendible:** *«El sobrecoste computacional del mecanismo adaptativo representa menos del 1.8% del tiempo de ejecución total, confirmando la eficiencia del orquestador.»*

---

### Afirmación 6: «El perfil btnk_high causa menores valores de HV»
- **Dictamen:** **PARCIALMENTE RESPALDADA.**
- **Evidencia experimental:**
  - Descriptivamente, las instancias `btnk_high` presentan menores valores de HV ($0.796 - 0.849$) frente a perfiles como `tard_med` ($0.954 - 1.048$).
  - Sin embargo, las cotas de normalización analíticas se calculan de manera independiente para cada instancia. Con solo 2 instancias con perfil `btnk_high` en la muestra de 10, no es estadísticamente riguroso afirmar causalidad aislada del perfil sin controlar por el efecto específico de la instancia base.
- **Redacción defendible:** *«Dentro de la muestra analizada, las instancias asociadas al perfil de cuello de botella exhibieron descriptivamente valores inferiores de Hypervolume relativo a sus cotas analíticas, si bien el tamaño de muestra no permite inferir causalidad estructural independiente.»*

---

### Afirmación 7: «El portafolio no puede competir sin transferencia de soluciones»
- **Dictamen:** **NO DEMOSTRADA.**
- **Evidencia experimental:**
  - El resultado demuestra que *este diseño específico* (3 brazos fijos, bloques de 50 FE, $W=10$, $c=0.07$, $\Delta HV$ puro, archivo pasivo) no superó a los algoritmos continuos. No demuestra que *ningún portafolio* sin transferencia pueda competir bajo otras parametrizaciones, otros brazos o presupuestos mucho mayores.
- **Redacción defendible:** *«Bajo la configuración evaluada en la Fase 2, el portafolio pasivo sin transferencia de soluciones no logró superar a los algoritmos individuales continuos bajo presupuestos de 1.000, 3.000 y 5.000 FE.»*
