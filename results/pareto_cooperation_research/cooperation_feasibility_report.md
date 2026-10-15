# Informe de Viabilidad Técnica y Decisión sobre Cooperación Activa

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Fecha:** 2026-10-15  
**Entorno:** `mojssp-pareto-cooperation` (Commit `ea044c0`)

---

## 1. Viabilidad Técnica por Algoritmo

Los tres algoritmos comparten la **misma representación genotípica cerrada**:
$$\text{Solution} = (\pi_{\text{ops}}, v)$$
donde $\pi_{\text{ops}}$ es la permutación de operaciones basada en Bierwirth y $v$ es la tupla de modos discretos de velocidad de longitud $N = \sum n_j$, correspondiente exactamente a `instance.all_operations`.

A continuación se evalúa la compatibilidad interna de cada brazo para recibir soluciones externas provenientes del archivo global.

### 1.1. NSGA-II (`NSGA2Arm`)
- **Mecanismo Interno:** Mantiene una población $P_t$ de tamaño $N = 30$. Al final de cada generación, une padres e hijos ($R_t = P_t \cup Q_t$) y aplica `fast_non_dominated_sort()` y `calculate_crowding_distance()`.
- **Modo de Recepción:** Muy viable y directo. Una solución externa $x_{\text{ext}} = (sol, sched, objs)$ puede inyectarse directamente en $P_t$ reemplazando a un individuo del último frente de dominancia o con menor distancia de crowding.
- **Riesgos:**
  - *Colapso de diversidad:* Si las soluciones inyectadas dominan a la mayoría de la población local, pueden copar los frentes $F_1$ y $F_2$, empobreciendo el acervo genético propio de NSGA-II y provocando convergencia prematura.
  - *Control necesario:* Limitar la inyección a un número muy reducido ($k \le 2$) y asegurar que provengan de regiones poco densas.

### 1.2. MOEA/D (`MOEADArm`)
- **Mecanismo Interno:** Estructura rígida basada en subproblemas. Cada subproblema $j \in \{0, \dots, N-1\}$ posee un vector de peso fijo $\lambda_j$, una vecindad $B(j)$ y una única solución asociada $x_j$, evaluada mediante la función de agregación Tchebycheff:
  $$g^{te}(x \mid \lambda_j, z^*) = \max_{k \in \{1, 2, 3\}} \left\{ \lambda_j^k \cdot |f_k^{\text{norm}}(x) - z_k^*| \right\}$$
- **Modo de Recepción:** **Complejo y no trivial.** No es posible "añadir" un individuo arbitrariamente a la población sin romper la partición de pesos.
- **Procedimiento Requerido:**
  1. Para la solución candidata $x_{\text{ext}}$, se calcula su vector normalizado $f^{\text{norm}}(x_{\text{ext}})$.
  2. Se evalúa $g^{te}(x_{\text{ext}} \mid \lambda_j, z^*)$ para los subproblemas $j$.
  3. Se identifica el subproblema $j^*$ con mayor afinidad angular o mejor valor escalar.
  4. Si $g^{te}(x_{\text{ext}} \mid \lambda_{j^*}, z^*) < g^{te}(x_{j^*} \mid \lambda_{j^*}, z^*)$, se sustituye $x_{j^*}$ por $x_{\text{ext}}$, respetando el invariante de reemplazo acotado.
- **Riesgos:** Si se inserta una solución en un subproblema no afín, se deforma la distribución uniforme en el simplex de pesos que caracteriza a MOEA/D.

### 1.3. SPEA2 (`SPEA2Arm`)
- **Mecanismo Interno:** Mantiene una población $P_t$ y un archivo ambiental acotado $\bar{P}_t$ ($|\bar{P}_t| = N = 30$). Calcula el fitness asignando fuerza $S(i)$ y $R(i)$ más un término de densidad $D(i)$ basado en la distancia euclidiana al $k$-ésimo vecino ($k = \sqrt{N + \bar{N}}$). Si $|\bar{P}_{t+1}| > N$, aplica truncamiento iterativo por vecindad mínima.
- **Modo de Recepción:** Viable. Puede incorporarse a $\bar{P}_t$ o a $P_t$.
- **Riesgos:**
  - *Truncamiento inmediato:* Si la solución inyectada está cerca de soluciones existentes en $\bar{P}_t$, el algoritmo de truncamiento de SPEA2 la eliminará de inmediato en el siguiente paso ambiental, haciendo que la inyección sea inerte.
  - *Costo cuadrático:* Recalcular distancias euclidianas por pares sobre matrices aumentadas tiene costo $O((N + k)^2)$.

---

## 2. Contabilización Estricta de Evaluaciones de Función Objetivo (FE)

Un principio rector de la investigación es la **ausencia total de evaluaciones gratuitas**:

1. **Reutilización de Objetivos Válidos:**
   - La tupla $(sol, sched, objs)$ ya fue evaluada cuando se generó.
   - Si se copia exactamente esa tupla a la población receptora, **el coste es 0 FE adicionales**.
   - No se debe llamar a `Evaluator.evaluate()` ni decodificar nuevamente.
2. **Modificación de Candidatos Inyectados:**
   - Si el algoritmo receptor somete la solución inyectada a mutación o recombinación con individuos locales, el nuevo hijo resultante **sí debe evaluarse**, consumiendo estrictamente 1 FE del presupuesto del bloque.
3. **Sobrecosto Computacional:**
   - La transferencia no consume FE, pero introduce sobrecosto temporal en CPU (tiempo de pared) por operaciones de ordenamiento, cálculo de Tchebycheff y distancias. Este sobrecosto debe ser medido y reportado.

---

## 3. Respuestas a las Ocho Preguntas Metodológicas

1. **¿Los algoritmos encuentran soluciones complementarias?**  
   **SÍ.** La evidencia empírica en las 10 bases demuestra que el frente de unión retrospectiva supera al mejor algoritmo individual en promedio en $+0.92\%$ de Hypervolume a 5.000 FE, aportando decenas de soluciones exclusivas no compartidas por ningún otro algoritmo.

2. **¿La complementariedad también aparece dentro del portafolio compartido?**  
   **PARCIALMENTE.** El archivo global actual acumula las soluciones de todos los brazos, pero debido a la falta de comunicación entre poblaciones y a la fragmentación del presupuesto (cada brazo recibe $\approx 1/3$ del presupuesto), el rendimiento del portafolio pasivo actual es inferior al del mejor algoritmo individual standalone en $\approx 0.058$ HV.

3. **¿El archivo global aprovecha correctamente las soluciones que recibe?**  
   **SÍ.** Se verificó que el archivo global preserva el frente no dominado estricto, no pierde soluciones de brazos previos, respeta duplicados de objetivos con distinto genotipo y su Hypervolume es estrictamente monótono.

4. **¿Existen soluciones útiles que no llegan al archivo?**  
   **NO.** Cada brazo posee un archivo interno no acotado que registra todo candidato evaluado y lo entrega íntegramente al portafolio. Ninguna solución no dominada evaluada se pierde.

5. **¿Los genotipos son recuperables y transferibles?**  
   **EN MEMORIA SÍ (Nivel 2), EN ARCHIVOS PERSISTIDOS NO (Nivel 1).** Durante la ejecución, `ArchiveEntry` contiene el objeto `Solution` inmutable listo para transferirse. En los archivos JSONL persistidos en disco solo se almacenaron los vectores objetivo $(C_{max}, T, E)$.

6. **¿Qué dificultades existen en cada algoritmo?**  
   - MOEA/D exige proyección escalar Tchebycheff y mapeo cuidadoso a subproblemas afines.
   - NSGA-II corre riesgo de colapso de diversidad genética si se satura con individuos dominantes.
   - SPEA2 puede truncar inmediatamente soluciones inyectadas por densidad si no están suficientemente aisladas.

7. **¿Hay evidencia suficiente para justificar un experimento de cooperación activa?**  
   **SÍ, pero supeditada a una instrumentación previa rigurosa (Dictamen B).** La brecha empírica entre el Escenario A (unión retrospectiva) y el Escenario B (portafolio compartido) evidencia que las poblaciones aisladas sufren por la partición de evaluaciones. Transferir soluciones elite podría permitir que los brazos alcancen frentes de mayor calidad sin requerir más evaluaciones totales.

8. **¿Qué información falta?**  
   - Trazabilidad Nivel 3 (etiquetar `origin_arm` y `discovery_fe` en `ArchiveEntry`).
   - Mapeador formal de soluciones externas para subproblemas de MOEA/D.
   - Telemetría de diversidad fenotípica y genotípica post-inyección.

---

## 4. Propuesta Conceptual de un Único Mecanismo Inicial de Cooperación

Para una futura fase experimental, se propone un único mecanismo **minimalista, reversible y determinista**:

### "Inyección Elite Asimétrica al Inicio de Bloque" (Archive-to-Arm Injection)
- **Origen:** Exclusivamente el `Global Pareto Archive` acumulado.
- **Frecuencia:** Una única vez al inicio del bloque del algoritmo seleccionado, inmediatamente antes de reanudar su ciclo evolutivo.
- **Tasa de Inyección:** Exactamente $k = 1$ o $k = 2$ soluciones (máximo 6.6% de la población de $N = 30$).
- **Criterio de Selección de Candidatas:**
  - Se selecciona la solución del archivo global que maximice la distancia de crowding o que presente el mejor valor según el criterio del algoritmo receptor (para MOEA/D, la que mejore el subproblema con mayor error respecto al punto ideal $z^*$).
- **Destino e Inserción:**
  - En **NSGA-II:** sustituye al individuo de peor rango / menor crowding en $P_t$.
  - En **MOEA/D:** sustituye únicamente si mejora la función Tchebycheff de su subproblema más afín.
  - En **SPEA2:** sustituye al individuo de peor fitness en $P_t$.
- **Coste de FE:** **0 FE.** Se reutilizan `solution`, `schedule` y `objectives` ya evaluados.
- **Condición de Suspensión (Kill-Switch):** Si la diversidad poblacional (medida por distancia de Hamming o crowding promedio) decrece más de un 50% tras dos bloques consecutivos de inyección, la inyección se desactiva automáticamente para ese brazo durante el resto de la corrida.

