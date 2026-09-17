# Especificación Científica y Formulación Matemática del Modelo MO-JSSP con Speed Scaling

Este documento establece formalmente la especificación científica y el modelo matemático del **Multi-Objective Job Shop Scheduling Problem con Speed Scaling (MO-JSSP)** correspondiente a la **Fase 1** de la tesis:

> *"Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)"*

---

## 1. Definición de Instancia

Una instancia $\mathcal{I}$ define formalmente un entorno de manufactura Job Shop discreto y determinista con velocidad variable. Contiene:
* El conjunto de trabajos $\mathcal{J} = \{1, \dots, n\}$.
* El conjunto de máquinas físicas unarias $\mathcal{M} = \{1, \dots, m\}$.
* Para cada trabajo $j \in \mathcal{J}$, una ruta tecnológica secuencial de operaciones $\mathcal{O}_j$ con sus requerimientos de máquina, modos disponibles y fecha de entrega.

---

## 2. Definición de Operación

Una operación $O_{j,k}$ representa la $k$-ésima tarea elemental del trabajo $j$ ($k \in \{1, \dots, n_j\}$).
* Es atómica e indivisible.
* Requiere de manera determinista y exclusiva una máquina física $M_{j,k} \in \mathcal{M}$.
* Dispone de un conjunto finito de modos de procesamiento/velocidad $V_{j,k}$.
* Opcionalmente posee una fecha de liberación $r_{j,k} \ge 0$.

---

## 3. Definición de SpeedScaling

Cada operación $O_{j,k}$ requiere la selección de un modo de procesamiento o nivel de velocidad $v_{j,k} \in V_{j,k}$.
* El modo seleccionado determina simultáneamente dos parámetros:
  - Tiempo de procesamiento: $p_{j,k,v} \in \mathbb{Z}^+$ ($p_{j,k,v} > 0$).
  - Consumo energético: $e_{j,k,v} \in \mathbb{R}^+$ ($e_{j,k,v} \ge 0$).
* **Principio de Neutralidad Física**: El modelo no asume ni impone a priori que una mayor velocidad reduzca el tiempo o incremente la energía. La relación exacta proviene exclusivamente de los datos de cada instancia, garantizando total generalidad matemática.

---

## 4. Definición de Fechas de Liberación (Release Dates)

Para cada operación $O_{j,k}$, la fecha de liberación $r_{j,k} \in \mathbb{Z}_{\ge 0}$ determina el instante más temprano en el cual la operación está disponible para iniciar su procesamiento. En las instancias iniciales se considera $r_{j,k} = 0$, preservando el soporte en el modelo sin convertirlo en un eje experimental obligatorio.

---

## 5. Definición de Fechas de Entrega (Due Dates)

La fecha de entrega $d_j \in \mathbb{Z}_{\ge 0}$ se define formalmente **por trabajo**. Representa la fecha límite comprometida para finalizar la manufactura del producto completo (es decir, la culminación de su última operación $O_{j,n_j}$). Constituye una referencia blanda (*soft constraint*) cuyo incumplimiento genera una penalización por tardiness.

---

## 6. Restricciones de Factibilidad

Un schedule factible debe satisfacer las siguientes cuatro condiciones:

1. **Restricción de fecha de liberación (Release Date)**:
   Ninguna operación puede iniciar antes de su fecha de disponibilidad:
   $$S_{j,k} \ge r_{j,k}, \quad \forall j \in \mathcal{J}, \; k \in \{1, \dots, n_j\}$$

2. **Restricción de precedencia tecnológica dentro de cada trabajo**:
   Las operaciones de un mismo trabajo deben ejecutarse en orden estricto; una operación no puede comenzar antes de que su predecesora directa haya concluido:
   $$S_{j,k} \ge C_{j,k-1}, \quad \forall j \in \mathcal{J}, \; k \in \{2, \dots, n_j\}$$

3. **Restricción de no solapamiento en máquinas (Capacidad unaria)**:
   Cada máquina puede procesar a lo sumo una operación a la vez. Para cualquier par de operaciones distintas $O_{j,k}, O_{j',k'} \in \mathcal{O}$ con $(j,k) \ne (j',k')$ asignadas a la misma máquina ($M_{j,k} = M_{j',k'}$):
   $$S_{j,k} \ge C_{j',k'} \quad \lor \quad S_{j',k'} \ge C_{j,k}$$

4. **Restricción de no interrupción (*Non-preemption*)**:
   Una vez iniciada una operación, se procesa sin pausas hasta culminar:
   $$C_{j,k} = S_{j,k} + p_{j,k, v_{j,k}}$$

---

## 7. Makespan ($C_{\max}$)

El Makespan representa el tiempo total de finalización del programa de producción, determinado por la culminación del último trabajo:
$$C_{\max} = \max_{j \in \mathcal{J}} C_j = \max_{j \in \mathcal{J}} C_{j, n_j}$$
Es un objetivo de minimización.

---

## 8. Tardiness por Trabajo ($T$)

La tardiness mide el retraso acumulado de los trabajos respecto a sus fechas de entrega pactadas.
* Para cada trabajo $j \in \mathcal{J}$:
  $$T_j = \max(0, C_j - d_j)$$
  donde $C_j = C_{j,n_j}$ es el instante de finalización de la última operación del trabajo $j$.
* El objetivo canónico de la tesis es minimizar la tardiness total acumulada por trabajo:
  $$T = \sum_{j \in \mathcal{J}} T_j = \sum_{j \in \mathcal{J}} \max(0, C_j - d_j)$$

---

## 9. Consumo Energético Total ($E$)

El consumo total de energía corresponde a la suma de la energía consumida por todas las operaciones bajo sus respectivos modos de velocidad seleccionados:
$$E = \sum_{j \in \mathcal{J}} \sum_{k=1}^{n_j} e_{j,k, v_{j,k}}$$
Es un objetivo de minimización.

---

## 10. Formulación Multiobjetivo Verdadera

El problema es genuinamente multiobjetivo. No se combinan los objetivos mediante funciones escalares o sumas ponderadas. El propósito es aproximar el frente de Pareto no dominado que minimiza simultáneamente el vector:
$$\min \mathbf{F} = \left( C_{\max}, T, E \right)$$

---

## 11. Diferencias Respecto al Modelo MiniZinc de Referencia (`JSP2.mzn`)

| Aspecto | Modelo MiniZinc (`JSP2.mzn`) | Modelo Canónico de la Tesis (Python) | Justificación Metodológica |
| :--- | :--- | :--- | :--- |
| **Enfoque de Optimización** | Monobjetivo por suma escalar: `ob = makespan + consumedEnergy + tardiness` | Multiobjetivo vectorial estricto: $\min (C_{\max}, T, E)$ | Permite el análisis de soluciones no dominadas y frentes de Pareto, núcleo de la tesis. |
| **Definición de Tardiness** | Tardiness por operación truncada: $\sum \min(\max(0, C_{j,m}-d_{j,m}), p_{j,m})$ | Tardiness por trabajo: $T = \sum_j \max(0, C_j - d_j)$ | En manufactura, el cliente penaliza la entrega tardía del producto terminado ($j$), no de etapas intermedias. |
| **Fechas de Entrega** | Matriz 2D `dueDate[JOBS, MACHINES]` | Escalar por trabajo: $d_j$ para cada $j \in \mathcal{J}$ | Consistente con la evaluación por trabajo. Al importar de `.dzn`, $d_j$ adopta la fecha de la última operación de la ruta. |
| **SpeedScaling** | Arrays 3D indexados rígidamente `[JOBS, MACHINES, SPEED]` | Colección de `ProcessingMode` desacoplada | Permite flexibilidad y heterogeneidad de modos entre distintas operaciones. |
| **Rol en el Proyecto** | Modelo de referencia conceptual y validación auxiliar | Núcleo de la arquitectura experimental | El portafolio y los algoritmos adaptativos se implementarán y evaluarán en Python. |

---

## 12. Distinción Conceptual entre Instance y Solution

Es fundamental para la arquitectura del proyecto mantener una estricta separación de responsabilidades:

### Instance (Fase 1)
Entidad inmutable que define exclusivamente los parámetros y restricciones del problema:
* Trabajos ($\mathcal{J}$) y su secuencia de operaciones ($\mathcal{O}_j$).
* Máquinas asignadas ($M_{j,k}$).
* Modos disponibles ($V_{j,k}$) con duraciones ($p_{j,k,v}$) y consumos energéticos ($e_{j,k,v}$).
* Fechas de liberación ($r_{j,k}$) y fechas de entrega de los trabajos ($d_j$).
* *No contiene decisiones, schedules ni asignaciones temporales.*

### Solution (Fases posteriores)
Entidad que representa una solución candidata generada por un optimizador:
* Decisión de modo/velocidad para cada operación ($v_{j,k} \in V_{j,k}$).
* Secuenciación/ordenamiento de las operaciones en las máquinas.
* Mediante el **Decoder**, se determinan los tiempos de inicio ($S_{j,k}$) y finalización ($C_{j,k}$).
* Mediante el **Evaluador**, se obtienen los valores objetivos correspondientes: $(C_{\max}, T, E)$.
