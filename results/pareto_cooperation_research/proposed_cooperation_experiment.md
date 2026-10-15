# Diseño del Experimento Futuro: Cooperación Activa vs Portafolio Pasivo

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Fecha:** 2026-10-15  
**Entorno:** `mojssp-pareto-cooperation` (Commit `ea044c0`)

---

## 1. Objetivo Científico del Experimento Propuesto

Aislar y cuantificar de manera rigurosa el efecto de la **transferencia de soluciones elite (cooperación activa)** sobre la convergencia y calidad del frente de Pareto en el portafolio de 3 brazos, manteniendo idénticas todas las demás variables experimentales.

---

## 2. Esquema Experimental Controlado (Comparación Tripartita)

Para evitar sesgos y variables confundidas, el diseño contempla tres condiciones estrictamente pareadas:

```mermaid
flowchart TD
    subgraph Presupuesto Idéntico: B = 3000 FE
        CA["Control A: Portafolio Pasivo Original (DMAB SW-UCB)"]
        TB["Tratamiento B: Portafolio Cooperativo Activo (Misma secuencia de bloques de A)"]
        CC["Control C: Standalone Baselines (MOEA/D, NSGA-II, SPEA2 a 3000 FE)"]
    end
    CA --> M["Comparación de Métricas: HV, IGD+, Diversidad, % Aporte"]
    TB --> M
    CC --> M
```

### 2.1. Condición Control A (Portafolio Pasivo Actual)
- **Selector:** Sliding Window UCB ($W = 10$, $c = 0.07$).
- **Brazos:** MOEA/D, NSGA-II, SPEA2 ($N = 30$).
- **Presupuesto Total:** $B_{\text{total}} = 3.000$ FE.
- **Tamaño de Bloque:** $B = 50$ FE ($60$ bloques).
- **Interacción entre Brazos:** Cero comunicación poblacional; recolección exclusiva en `Global Pareto Archive`.

### 2.2. Condición Tratamiento B (Portafolio Cooperativo Activo)
- **Mecanismo:** Inyección Elite Asimétrica ($k = 2$ soluciones del archivo global al inicio de bloque).
- **Aislamiento de la Variable Cooperación:**
  - Para asegurar que una eventual diferencia en rendimiento no se deba a decisiones aleatorias distintas del DMAB, **el Tratamiento B ejecutará exactamente la misma secuencia de bloques y asignaciones de brazos que el Control A** (reproducción determinista de la traza de bloques de Control A).
  - De este modo, la asignación de presupuesto por brazo es 100% idéntica entre A y B; la única diferencia es la presencia o ausencia de la transferencia de soluciones.
- **Presupuesto Total:** $B_{\text{total}} = 3.000$ FE (reutilización de objetivos ya evaluados, 0 FE de coste por inyección).

### 2.3. Condición Control C (Standalones Puros)
- MOEA/D individual ejecutado a $3.000$ FE.
- NSGA-II individual ejecutado a $3.000$ FE.
- SPEA2 individual ejecutado a $3.000$ FE.

---

## 3. Protocolo de Ejecución y Muestra de Instancias

- **Instancias:** Las 10 bases independientes del split de desarrollo utilizadas en Fase 2 (`base_c01_5x5_b03` a `base_c08_50x50_b03`).
- **Semillas:** 3 semillas pareadas (`42`, `43`, `44`).
- **Punto de Referencia y Normalización:** Idéntico $(1.1, 1.1, 1.1)$ con cotas analíticas teóricas fijas.
- **Número Total de Corridas:** $10 \text{ instancias} \times 3 \text{ semillas} \times (1 + 1 + 3) = 150 \text{ ejecuciones}$.

---

## 4. Criterios de Decisión: Validación o Descarte del Mecanismo

Se definen a priori los criterios observables para determinar el éxito o fracaso de la cooperación activa:

### 4.1. Criterios de Éxito (Continuar con Cooperación Activa)
1. **Superioridad sobre Control A:** $HV(B) > HV(A)$ de forma estadísticamente significativa mediante prueba pareada de rangos con signo de Wilcoxon sobre las 10 bases ($p < 0.05$) y tamaño de efecto positivo ($d > +0.5$).
2. **Reducción de la Brecha frente a Standalones:** El Tratamiento B debe acortar significativamente la brecha negativa de $-0.051$ HV que el portafolio pasivo actual exhibe frente al mejor standalone a 3.000 FE.
3. **Preservación de Diversidad:** La tasa de contribución efectiva al archivo global final debe mantenerse equilibrada ($\min_i \% \text{contribución}(A_i) \ge 15\%$), demostrando que ningún algoritmo canibalizó por completo a los otros.

### 4.2. Criterios de Fracaso (Descartar Cooperación Activa)
1. **Colapso de Diversidad:** Una de las poblaciones receptoras pierde más del 60% de su varianza genética o el portafolio se estanca prematuramente en un óptimo local temprano.
2. **Degradación del Hypervolume:** $HV(B) \le HV(A)$ o incremento de tiempo de CPU superior al 30% sin mejora detectable en calidad del frente.
3. **Violación de Invariantes:** Desajuste en la descomposición de MOEA/D o aumento de evaluaciones por encima de las $3.000$ FE prescritas.

---

## 5. Estado de Ejecución
Este diseño experimental queda formalmente registrado como propuesta metodológica. **No debe ejecutarse** hasta que se aprueben los dictámenes y se implemente la instrumentación de procedencia (Nivel 3).

