# Dictamen de Cierre Formal de la Fase 2

Este documento emite el dictamen oficial de cierre metodológico y técnico para la Fase 2 del proyecto de tesis:

**«Portafolio Algorítmico Aplicado al Problema de Programación de Job Shop Multiobjetivo (MO-JSSP)»**

---

## 1. Dictamen Oficial

```
┌─────────────────────────────────────────────────────────────┐
│                 DICTAMEN METODOLÓGICO:                      │
│                    CIERRE APROBADO                          │
└─────────────────────────────────────────────────────────────┘
```

El dictamen previo **APTO CON OBSERVACIONES** (emitido en F2.5.2) ha sido satisfactoriamente resuelto mediante la subsanación formal de todas las observaciones técnicas y metodológicas verificables:
1. **Reconstrucción algorítmica exacta de SW-UCB:** Se confirmó la reproducción exacta del 100% (2.910 de 2.910 decisiones) de la serie de selecciones registradas en los experimentos reales, verificando la influencia dominante de la exploración (ratio $35.4\times$) y la tasa de inversión por exploración ($64.11\%$).
2. **Corrección de la atribución temporal:** Se documentó formalmente la ausencia de instrumentación de profiling fino interno y se sustituyó la afirmación por mediciones directas de tiempo de pared macroscópico (diferencia acumulada de $-0.21\%$ entre DMAB y Uniforme).
3. **Deslinde riguroso de frentes y complementariedad:** Se distinguió con precisión la unión de ejecuciones independientes continuas ($3 \times 5.000 = 15.000$ FE) del archivo consolidado de un portafolio bajo presupuesto compartido (5.000 FE totales), clarificando la no aditividad de las contribuciones marginales de Hypervolume.
4. **Acotamiento epistemológico y eliminación de sesgos causales:** Se reformularon las 7 afirmaciones de F2.5.1 en [`f2_6_claims_matrix.csv`](file:///c:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-dmab/results/expanded_portfolio_phase2/final_closure/f2_6_claims_matrix.csv), eliminando afirmaciones causales no probadas sobre la fragmentación poblacional y encuadrando la inyección de soluciones y el test Page-Hinkley como hipótesis de investigación para la Fase 3.
5. **Precisión en la estructura experimental:** Se corrigieron las referencias a 450 corridas independientes, especificando que se trata de 150 trayectorias continuas con 450 registros de hitos presupuestarios distribuidas en 8 configuraciones dimensionales y 10 instancias base independientes.
6. **Aprobación de la suite de software:** Las **375 pruebas unitarias e integrales** pasaron satisfactoriamente (100% OK en 15.74s).

---

## 2. Cumplimiento de los Criterios de Aceptación

| Criterio de Aceptación | Estado | Evidencia de Verificación |
| :--- | :---: | :--- |
| **1. Integridad de los resultados originales** | **CUMPLIDO** | 150 trayectorias continuas con 450 registros de hitos en `budget_runs.csv` y 15.000 checkpoints sin alteraciones ni pasos no monótonos. Coherencia bit a bit F2.4 vs F2.5.1 confirmada ($\Delta HV = 0.0$). |
| **2. Ausencia de discrepancias críticas** | **CUMPLIDO** | `max_generations=None` auditado y defendido como solución técnica indispensable con impacto nulo en 1.000 FE. Reproducción del 100% de las 2.910 decisiones de SW-UCB confirmada. |
| **3. Estructura estadística rigurosa** | **CUMPLIDO** | Inferencia jerárquica sobre 10 bases independientes ($N=10$, $df=9$), corrección de Holm-Bonferroni para la familia principal y FDR Benjamini-Hochberg para comparaciones exploratorias. Términos corregidos a "sin diferencia estadísticamente significativa detectada" en 1.000 FE. |
| **4. Afirmaciones debidamente acotadas** | **CUMPLIDO** | 7 afirmaciones auditadas y reformuladas formalmente en `f2_6_claims_matrix.csv`. Sin sobreafirmaciones de superioridad ni aserciones causales no probadas. |
| **5. Trazabilidad experimental y de código** | **CUMPLIDO** | Manifiesto de reproducibilidad completo generado en `f2_6_reproducibility_manifest.json` registrando versiones, commits, parámetros, semillas, 8 configuraciones y 10 bases. |
| **6. Pruebas de software aprobadas** | **CUMPLIDO** | Suite `unittest` aprobada al 100% (375 pruebas ejecutadas, 375 OK en 15.74s). |
| **7. Limitaciones arquitectónicas explícitas** | **CUMPLIDO** | Documentación de la menor convergencia del portafolio pasivo frente a continuos y planteamiento de la inyección y Page-Hinkley como hipótesis teóricas a evaluar en Fase 3. |
| **8. Línea base congelable identificable** | **CUMPLIDO** | Especificación técnica congelada documentada en el manifiesto y en la sección 3 de este documento. |

---

## 3. Línea Base Congelable para Experimentos Posteriores

Para garantizar la reproducibilidad y la comparabilidad experimental en la Fase 3, se declara formalmente **congelada** la siguiente configuración arquitectónica y paramétrica como línea base de referencia:

```text
================================================================================
           LÍNEA BASE EXPERIMENTAL CONGELADA (FASE 2 -> FASE 3)
================================================================================

1. ARQUITECTURA DE BRAZOS (3 BRAZOS FIJOS):
   - Brazo 1: MOEA/D  (pop_size=30, n_neighbors=6, cr=1.0, mr=0.1, Tchebycheff)
   - Brazo 2: NSGA-II (pop_size=30, cr=0.9, mr=0.1, max_generations=None)
   - Brazo 3: SPEA2   (pop_size=30, archive_size=30, cr=0.9, mr=0.1)

2. DECODIFICACIÓN Y EVALUACIÓN DEL PROBLEMA:
   - Decoder: Serial List-Based Decoder determinista semi-activo (O(N)).
   - Evaluador: Función pura independiente sin estado.
   - Objetivos: Minimización estricta de (Makespan, Tardiness, Consumo Energético).
   - Normalización: Dinámica analítica por instancia mediante compute_instance_bounds().
   - Punto de referencia Hypervolume: [1.1, 1.1, 1.1] en espacio normalizado.

3. PROTOCOLO DE ORQUESTACIÓN Y PRESUPUESTO:
   - Granularidad de bloque: 50 Evaluaciones de la Función Objetivo (FE) por bloque.
   - Contabilidad de presupuesto: Estricta (overshoot = 0).
   - Fase de arranque:
     * Bloques 0 a 2 (Warm-up neutro): 1 bloque por brazo en orden canónico.
       Actualiza el Archivo Global Pareto, pero NO actualiza estadísticas DMAB.
     * Bloques 3 a 5 (Sondeo inicial): 1 bloque adaptativo por brazo en orden canónico.
       Registra la primera observación en la ventana de SW-UCB.
     * Bloques 6 en adelante: Selección adaptativa plena.

4. POLÍTICAS DE REFERENCIA:
   - Asignación Uniforme: RoundRobinSelector cíclico determinista.
   - Asignación Adaptativa: SlidingWindowUCB (W = 10, c = 0.07).
   - Señal de Recompensa: reward = max(0.0, Delta_HV_global).
   - Modo de Archivo: Global Pareto Archive pasivo (sin inyección entre poblaciones).

5. CONJUNTO DE DESARROLLO Y SEMILLAS:
   - 8 Configuraciones dimensionales (C1_5x5 a C8_50x50).
   - 10 Instancias base de desarrollo (con perfiles base, tard_med, tard_high, nrg_strong, btnk_high).
   - Semillas maestras: 42, 43, 44 (con derivación pseudoaleatoria determinista para cada brazo).
   - Instancias Holdout: ESTRICTAMENTE CONSERVADAS SIN ACCESO.
================================================================================
```

Toda investigación en la Fase 3 sobre:
- Migración o inyección de soluciones élite (F3.1),
- Recompensa multiescala o progreso poblacional (F3.2),
- Calibración de parámetros de exploración $c$ (F3.3), o
- Detección de cambios mediante Page-Hinkley (F3.4),

deberá contrastarse contra esta línea base congelada utilizando idénticos protocolos de evaluación e instancias de desarrollo antes de acceder al conjunto final de prueba (*holdout test*).
