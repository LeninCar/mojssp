# Informe de Corrección de Métricas de Complementariedad Histórica (P3.5-A)

**Proyecto:** Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)  
**Autor:** Antigravity (Auditoría Técnica Independiente)  
**Fecha:** 2026-10-15  
**Entorno de Trabajo:** Worktree Aislado `mojssp-pareto-cooperation` (Rama `experiment/pareto-archive-cooperation`, Commit `ea044c0`)

---

## 1. Justificación Matemática y Diagnóstico del Error Heredado

En la Fase 2, el script de cierre [`scripts/audit_phase2_closure.py`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/scripts/audit_phase2_closure.py#L376-L390) calculó la contribución marginal de cada algoritmo a la unión de la siguiente manera:

```python
# Código heredado de Fase 2 (audit_phase2_closure.py, líneas 376-380):
union_minus_m = [p for p in union_nd if p not in m_pts]
hv_minus_m = compute_hypervolume(union_minus_m)
marginal_hv_m = max(0.0, hv_total_union - hv_minus_m)
```

### 1.1. La Falla Conceptual
El conjunto `union_nd` ($U$) es el frente no dominado obtenido tras filtrar conjuntamente las soluciones de los tres algoritmos:
$$U = ND(A_{\text{MOEA/D}} \cup A_{\text{NSGA-II}} \cup A_{\text{SPEA2}})$$
Al restar simplemente `m_pts` de `union_nd`, se obtiene $U \setminus A_{\text{MOEA/D}}$, el cual **omite** todas aquellas soluciones de NSGA-II y SPEA2 que habían sido dominadas por MOEA/D en el frente conjunto.

Sin embargo, según la **definición matemática canónica**, la contribución marginal de un algoritmo $i$ es la ganancia que aporta su presencia frente a lo que habrían logrado los otros algoritmos en su ausencia:
$$MC_i^{\text{canonical}} = HV(U) - HV\left(ND\left(\bigcup_{j \ne i} A_j\right)\right)$$

Al retirar formalmente a MOEA/D de la contienda, las soluciones de NSGA-II y SPEA2 previamente dominadas por MOEA/D **recuperan su condición de no dominadas** en $ND(A_{\text{NSGA-II}} \cup A_{\text{SPEA2}})$.

Dado que:
$$U \setminus A_i \subseteq ND\left(\bigcup_{j \ne i} A_j\right) \implies HV(U \setminus A_i) \le HV\left(ND\left(\bigcup_{j \ne i} A_j\right)\right)$$

se concluye rigurosamente que:
$$MC_i^{\text{closure}} \ge MC_i^{\text{canonical}}$$

El script de la Fase 2 **sobreestimó sistemáticamente** la contribución marginal de los algoritmos.

---

## 2. Recálculo Canónico Riguroso sobre los 90 Casos

Se implementó el recálculo canónico directo utilizando:
1. Los frentes de Pareto 3D originales de `results/expanded_portfolio_phase2/budget_diagnostic/budget_fronts.jsonl`.
2. Las cotas min-max analíticas exactas de cada instancia calculadas mediante `compute_instance_bounds(instance)`.
3. El punto de referencia canónico fijado en $(1.1, 1.1, 1.1)$.
4. El operador formal de no dominancia $ND(\cdot)$ recalculado sobre la unión de los otros dos algoritmos.

### 2.1. Comparación Agregada por Presupuesto (Media de 30 corridas por presupuesto)

| Presupuesto | Algoritmo | $MC_i^{\text{closure}}$ (Fase 2 Heredado) | $MC_i^{\text{canonical}}$ (Corregido) | Sobreestimación Promedio |
| :---: | :---: | :---: | :---: | :---: |
| **1.000 FE** | **MOEA/D** | $0.064126$ | **$0.011384$** | $+0.052742$ |
| | **NSGA-II** | $0.004748$ | **$0.003728$** | $+0.001020$ |
| | **SPEA2** | $0.036566$ | **$0.003252$** | $+0.033314$ |
| **3.000 FE** | **MOEA/D** | $0.046139$ | **$0.021573$** | $+0.024566$ |
| | **NSGA-II** | $0.003720$ | **$0.003043$** | $+0.000677$ |
| | **SPEA2** | $0.009373$ | **$0.003826$** | $+0.005547$ |
| **5.000 FE** | **MOEA/D** | $0.088316$ | **$0.030796$** | $+0.057520$ |
| | **NSGA-II** | $0.005342$ | **$0.003065$** | $+0.002277$ |
| | **SPEA2** | $0.010232$ | **$0.003849$** | $+0.006383$ |

---

## 3. Comprobación de Propiedades Matemáticas del Conjunto Corregido

Se verificaron las siguientes propiedades matemáticas sobre la totalidad de los 90 casos en `canonical_complementarity_metrics.csv`:

1. **No-negatividad de las Contribuciones Marginales:**
   $$\forall i \in \{\text{MOEA/D}, \text{NSGA-II}, \text{SPEA2}\}: MC_i^{\text{canonical}} \ge 0.0$$
   - Mínimo observado en dataset: `0.0` (cero violaciones de monotonicidad de dominancia).
2. **Dominancia del Frente Unión:**
   $$HV(U) \ge \max\left(HV(A_{\text{MOEA/D}}), HV(A_{\text{NSGA-II}}), HV(A_{\text{SPEA2}})\right)$$
   - Casos con $\Delta HV < -10^{-12}$: **0**.
3. **No-aditividad de las Contribuciones Marginales:**
   - La suma $\sum_i MC_i^{\text{canonical}}$ no equivale a $HV(U)$, confirmando que existen regiones del espacio objetivo donde dos algoritmos solapan su cobertura volumétrica.
4. **Persistencia de la Superioridad de MOEA/D:**
   - Aunque su magnitud se redujo de $0.088$ a $0.031$ a 5.000 FE, **MOEA/D sigue siendo el mayor contribuyente marginal exclusivo**, aportando aproximadamente 10 veces más volumen hipergeométrico exclusivo que NSGA-II y SPEA2.

---

## 4. Trazabilidad de Archivos Actualizados

Los datos corregidos y sus campos de comparación fueron exportados a:
- [`results/pareto_cooperation_research/canonical_complementarity_metrics.csv`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/results/pareto_cooperation_research/canonical_complementarity_metrics.csv)
- [`results/pareto_cooperation_research/complementarity_metrics.csv`](file:///C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-pareto-cooperation/results/pareto_cooperation_research/complementarity_metrics.csv)

Ambos archivos conservan las columnas `closure_mc_*` y `canonical_mc_*` en paralelo para garantizar la plena auditoría histórica.

