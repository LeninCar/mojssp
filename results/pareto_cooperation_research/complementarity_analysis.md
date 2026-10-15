# Análisis Cuantitativo de Complementariedad entre MOEA/D, NSGA-II y SPEA2

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Dataset Base:** `budget_diagnostic` (450 corridas, 10 bases, 3 semillas, presupuestos 1.000, 3.000 y 5.000 FE)  
**Fecha:** 2026-10-15  
**Entorno:** `mojssp-pareto-cooperation` (Commit `ea044c0`)

---

## 1. Definiciones Matemáticas y Protocolo de Evaluación

Para cada instancia $inst$, semilla $s$ y presupuesto $B \in \{1000, 3000, 5000\}$, se consideran los frentes no dominados generados por los tres algoritmos en ejecución standalone:
- $A_{\text{MOEA/D}}$
- $A_{\text{NSGA-II}}$
- $A_{\text{SPEA2}}$

### 1.1. Unión Retrospectiva y Ganancia de Complementariedad
Se construye el frente no dominado conjunto:
$$U = ND(A_{\text{MOEA/D}} \cup A_{\text{NSGA-II}} \cup A_{\text{SPEA2}})$$
$$HV_U = HV(U)$$

La ganancia absoluta y relativa respecto al mejor algoritmo individual en esa instancia y semilla son:
$$\Delta HV = HV_U - \max_{i \in \{\text{MOEA/D}, \text{NSGA-II}, \text{SPEA2}\}} HV(A_i)$$
$$\Delta HV_{\text{rel}} = \frac{\Delta HV}{\max_i HV(A_i)} \times 100\%$$

### 1.2. Contribución Marginal por Algoritmo
Para aislar el impacto exclusivo de cada algoritmo $i$, se calcula su contribución marginal al Hypervolume de la unión:
$$MC_i = HV(U) - HV\left(ND\left(\bigcup_{j \ne i} A_j\right)\right)$$

Propiedades matemáticas verificadas:
1. $HV_U \ge \max_i HV(A_i)$, garantizado por la definición de Hypervolume en minimización ($A_i \subseteq U \implies HV(U) \ge HV(A_i)$).
2. $MC_i \ge 0$, salvo micro-tolerancias numéricas ($\le 10^{-12}$).
3. La suma de contribuciones marginales $\sum_i MC_i \ne HV_U$, debido a que las regiones solapadas no se contabilizan en ninguna contribución marginal si dos algoritmos cubren la misma zona.
4. Tener soluciones exclusivas en $U$ **no garantiza** una contribución marginal positiva si dichas soluciones aportan un volumen hipergeométrico despreciable frente a los límites de referencia.

---

## 2. Resultados Agregados por Presupuesto

A continuación se resumen los promedios empíricos calculados sobre los 90 casos (10 instancias $\times$ 3 semillas $\times$ 3 presupuestos), disponibles detalladamente en `complementarity_metrics.csv`:

| Métrica Promedio | Presupuesto 1.000 FE | Presupuesto 3.000 FE | Presupuesto 5.000 FE |
| :--- | :---: | :---: | :---: |
| **Tamaño Frente Unión ($|U|$)** | $36.83 \pm 14.2$ | $65.57 \pm 31.8$ | $88.63 \pm 41.5$ |
| **Soluciones Exclusivas MOEA/D** | $17.43$ ($47.3\%$) | $30.43$ ($46.4\%$) | $41.90$ ($47.3\%$) |
| **Soluciones Exclusivas NSGA-II** | $8.40$ ($22.8\%$) | $12.13$ ($18.5\%$) | $18.23$ ($20.6\%$) |
| **Soluciones Exclusivas SPEA2** | $11.00$ ($29.9\%$) | $23.00$ ($35.1\%$) | $28.50$ ($32.1\%$) |
| **Soluciones Compartidas ($\ge 2$ algs)** | $0.00$ ($0.0\%$) | $0.00$ ($0.0\%$) | $0.00$ ($0.0\%$) |
| **Ganancia Absoluta $\Delta HV$** | $+0.00649$ | $+0.00862$ | $+0.00955$ |
| **Ganancia Relativa $\Delta HV_{\text{rel}}$** | $+0.68\%$ | $+0.86\%$ | $+0.92\%$ |
| **Contribución Marginal MOEA/D ($MC$)** | $0.06413$ | $0.04614$ | $0.08832$ |
| **Contribución Marginal NSGA-II ($MC$)** | $0.00475$ | $0.00372$ | $0.00534$ |
| **Contribución Marginal SPEA2 ($MC$)** | $0.03657$ | $0.00937$ | $0.01023$ |
| **Brecha Escenario A vs Escenario B** | $+0.04765$ | $+0.06012$ | $+0.06785$ |
| **DMAB vs Mejor Standalone** | $-0.04116$ | $-0.05151$ | $-0.05830$ |

---

## 3. Hallazgos Clave

### 3.1. Evidencia Sólida de Complementariedad Espacial (Escenario A)
- **Cero soluciones compartidas en el frente combinado:** En ninguna de las 90 evaluaciones los algoritmos descubrieron idénticos vectores objetivo en el frente no dominado conjunto ($shared = 0$). Debido a la naturaleza combinatoria de los modos de velocidad y las secuencias en espacio continuo de objetivos $(C_{max}, T, E)$, cada algoritmo explora trayectorias ortogonales.
- **Distribución de Soluciones:**
  - **MOEA/D** es el mayor contribuyente volumétrico y numérico ($46\% - 47\%$ de las soluciones del frente unión), con un $MC_{\text{MOEA/D}}$ dominante en la mayoría de los casos. Sus vectores de peso forzan la búsqueda hacia extremos de tardanza y energía que los otros métodos no alcanzan con igual profundidad.
  - **SPEA2** aporta entre un $30\%$ y $35\%$ de las soluciones exclusivas, capturando regiones intermedias con excelente densidad gracias a su estimador $k$-NN.
  - **NSGA-II** aporta aproximadamente el $20\%$ de las soluciones exclusivas, concentrándose en el centro del frente pero mostrando menor contribución marginal en volumen ($MC \approx 0.004 - 0.005$).

### 3.2. La Paradoja del Presupuesto Compartido (Escenario A vs Escenario B)
Es imperativo distinguir científicamente ambos escenarios:

```text
Escenario A (Unión Retrospectiva):
MOEA/D (5.000 FE) + NSGA-II (5.000 FE) + SPEA2 (5.000 FE) = 15.000 FE Acumuladas
Resultado: HV_U = 1.135 (Promedio)

Escenario B (Portafolio Compartido Actual - Cooperación Pasiva):
MOEA/D (~1.666 FE) + NSGA-II (~1.666 FE) + SPEA2 (~1.666 FE) = 5.000 FE Totales
Resultado: HV_DMAB = 1.067 (Promedio)

Brecha: HV_U - HV_DMAB = +0.06785 (El portafolio rinde MENOS que la unión retrospectiva)
```

- **Por qué el portafolio compartido rinde por debajo del mejor standalone:**
  - En un presupuesto total fijo de 5.000 FE, el portafolio actual divide los recursos entre los tres brazos.
  - Cada brazo corre en **aislamiento poblacional total**; sus poblaciones internas nunca intercambian información.
  - Como cada algoritmo solo recibe $\approx 1.666$ evaluaciones, ninguno alcanza la madurez de convergencia que alcanza un standalone ejecutado a 5.000 evaluaciones.
  - **Conclusión científica fundamental:** El archivo Pareto global actual realiza una *cooperación pasiva* (recolecta frentes al final de cada bloque), pero **no transfiere conocimiento a las poblaciones en evolución**. Esta brecha justifica formalmente la exploración de la *cooperación activa* (transferencia de soluciones).

---

## 4. Análisis por Características de Instancias

Al desglosar los resultados según el perfil de instancia (tratando los perfiles derivados de la misma base como condiciones relacionadas):

1. **Perfiles con Alta Presión de Tardanza (`tard_high`, `tard_med`):**
   - MOEA/D muestra su mayor ventaja competitiva. La presencia de subproblemas orientados específicamente a minimizar la tardanza evita que el algoritmo se estanque en trade-offs energéticos secundarios.
2. **Perfiles con Fuerte Conflicto Energético (`nrg_strong`):**
   - SPEA2 y NSGA-II muestran mayor cantidad de soluciones no dominadas exclusivas, debido a que el ajuste fino de modos de velocidad en operaciones no críticas es explorado eficientemente mediante mutación local.
3. **Escalamiento con la Dimensión del Problema ($N \times M$):**
   - En instancias pequeñas ($5 \times 5$, 25 ops), la unión retrospectiva satura rápidamente el frente ($\Delta HV_{\text{rel}} \approx 0.6\%$).
   - En instancias grandes ($30 \times 20$ y $50 \times 50$, hasta 2500 ops), la diversidad de los frentes aumenta notablemente, y el frente unión supera con mayor margen a los standalones, lo que indica que en problemas complejos la complementariedad es aún más pronunciada.

