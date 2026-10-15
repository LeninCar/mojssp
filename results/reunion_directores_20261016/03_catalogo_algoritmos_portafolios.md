# Catálogo de algoritmos y políticas

| Versión | Selección / asignación | Información compartida | Evidencia | Estado |
| --- | --- | --- | --- | --- |
| Histórico NSGA-II/MOPSO/NSGA-II+LS | SW-UCB y uniforme; brazos anteriores | Unión pasiva; búsqueda local sólo dentro de su brazo | 500/1000 FE; campañas F8 | Antecedente; no mezclar con los tres brazos actuales |
| MOEA/D, NSGA-II, SPEA2 individuales | Un brazo usa todo B | Sin intercambio | 1000, 3000, 5000; reciente 3000 | Controles vigentes |
| Uniforme RR | Bloques cíclicos de 50 FE | Archivo global como salida | Fase 2 y reciente | Control de fragmentación y agregación |
| SW-UCB original | Media ΔHV + bono; W=10,c=.07 | Archivo global mide recompensa; sin padre externo | Fase 2, PH y reciente | Línea base conservada |
| UCB1 acumulativo | Media de todas las recompensas + bono | Sin transferencia genética | PH: 5000 FE, 10 bases × 3 semillas | Control de olvido |
| UCB1 + Page-Hinkley C5 | Alarma reinicia crédito; δ=.0005, λ=.020 | Poblaciones y archivo se conservan | 270 calibración + 90 comparación, 5000 FE | No adoptado; sin ventaja corregida |
| UCB escalado | Media ΔHV / máximo reciente + mismo bono | Sin cooperación genética | 6 desarrollo y 8 confirmación, 3000 FE | Mejora reproducible frente a SW-UCB |
| Padre externo con replay | Copia exactamente la asignación del control SW-UCB | Un padre extranjero cada 10 cruces elegibles | 6 desarrollo y 8 confirmación, 3000 FE tratamiento | Evidencia condicional; coste del control adicional |
| Escalado + padre externo | Decisiones online con crédito escalado | Mismo mecanismo de padre externo | Sólo 6 desarrollo × 3 semillas, 3000 FE | No adoptado; sin ganancia adicional clara |
| SW-UCB c=.01/.03 (P5 paralelo) | Reducir el bono sin escalar crédito | Unión pasiva | 2 bases × una semilla; 1000 FE | Sensibilidad exploratoria; ver apéndice 32 |
| Inyección acotada P6/P7 paralela | SW-UCB c=.01 y secuencia fija | Hasta 2 incumbentes evaluados por bloque desde índice 6 | P6: 2 bases × una semilla; P7 parcial 1000 FE | Distinta de padre externo; corte externo separado |

## Componentes individuales

**MOEA/D** descompone objetivos mediante Tchebycheff sobre valores normalizados, \(g(x|w,z^*)=\max_k w_k|z_k(x)-z_k^*|\), con el tratamiento de pesos nulos definido en código. Mantiene subproblemas, ideal y vecinos. En la campaña reciente: población 30, vecinos 6, probabilidad de selección local .9, máximo dos reemplazos y cruce 1.0.

**NSGA-II** aplica ordenamiento no dominado, crowding y selección ambiental elitista; conserva descendencia parcial al pausar un bloque. La población experimental es 30, aunque el constructor tiene otro valor predeterminado. Cruce .9. **SPEA2** utiliza fuerza S(i), fitness crudo R(i)=ΣS(j) de quienes dominan i y densidad 1/(σᵏ+2), k=floor(√n), con truncación de vecinos en objetivos normalizados. Población y archivo ambiental experimentales 30; cruce .9.

Los tres usan POX, intercambio de secuencia con probabilidad .2 y mutación de modo por gen 1/N en el código auditado. Un documento histórico menciona mutación .1, pero no es una especificación suficiente: el runner histórico invoca los constructores y la instantánea reciente establece el parámetro efectivo. No se homogenizaron operadores para esta auditoría.

Las diferencias de selección hacen razonable estudiar complementariedad; no garantizan regiones exclusivas ni superioridad del conjunto. Referencias originales: [MOEA/D](https://doi.org/10.1109/TEVC.2007.892759), [NSGA-II](https://doi.org/10.1109/4235.996017), [SPEA2, TIK 103](https://sop.tik.ee.ethz.ch/publicationlistfiles/zlt2001a.pdf). Son fundamento conceptual, no evidencia del comportamiento de esta implementación.


## Fórmulas auditadas

Se normaliza cada objetivo con cotas analíticas de **esa instancia**, fijas durante una corrida:
\[
z_k=(f_k-L_k)/(U_k-L_k),\quad R=(1.1,1.1,1.1).
\]
Si la cota coincide se asigna cero, comprobando primero la pertenencia al intervalo. No se permite recortar violaciones reales para mejorar el indicador. La cota inferior de Cmax es \(\max_{j,k}(r_{jk}+\sum_{h\ge k}\min_v p_{jhv})\); la superior es \(\max r+\sum_o\max_v p_{ov}\). Energía usa suma de mínimos/máximos; tardanza inferior cero y superior \(\sum_j\max(0,U_C-d_j)\). Las cotas pueden ser muy conservadoras. El HV máximo teórico de la caja normalizada y referencia es 1.331: **HV > 1 es válido**.

\[
HV(A)=\operatorname{vol}\left(\bigcup_{z\in ND(A)}[z_1,R_1]\times[z_2,R_2]\times[z_3,R_3]\right),\quad
r_t=\max(0,HV(A_t)-HV(A_{t-1})).
\]

La recompensa usada por UCB es ΔHV por bloque, no ΔHV/FE. El diagnóstico puede dividir por 50 FE, pero no cambia la señal registrada. Para SW-UCB original:
\[
U_i(t)=\bar r_{i,W}+c\sqrt{\log(\min(t,W))/n_{i,W}},\quad W=10,\ c=0.07.
\]
La ventana contiene las últimas W observaciones **globales**, no W observaciones por brazo. Un brazo ausente tiene UCB infinito; empates usan RNG sembrado. Tras warmup se garantiza un probe por brazo. UCB1 usa media y recuento acumulativos, con log(t) en lugar de la ventana. Uniforme RR ignora recompensas y rota determinísticamente.

En escalado se conservan recompensas crudas y se calcula al decidir:
\[
s_t=\max_{(i,r)\in W}|r|\quad(1\text{ si todos son cero}),\qquad
U_i^{esc}=\bar r_{i,W}/s_t+c\sqrt{\log(\min(t,W))/n_{i,W}}.
\]
Es un denominador común de la ventana actual, también para recompensas antiguas aún vigentes. No es normalización independiente por brazo ni una implementación de FRRMAB.

PH de descenso usa la media acumulada actualizada \(\bar r_t\), \(m_t=m_{t-1}+\bar r_t-r_t-\delta\), \(M_t=\min(M_{t-1},m_t)\), alarma si \(m_t-M_t>\lambda\) tras mínimo de observaciones. C5: δ=.0005, λ=.020, UCB1 c=.07. Reinicia crédito, no poblaciones ni archivo; el resondeo consume 150 FE del presupuesto regular. No es SW-UCB más PH.

La AUC reciente es el promedio trapezoidal del HV a lo largo de B FE:
\[
AUC_B=\frac1B\sum_t(FE_t-FE_{t-1})\frac{HV_t+HV_{t-1}}2,\quad (FE_0,HV_0)=(0,0).
\]
No es un área normalizada por el mejor algoritmo ni un AUC temporal. Mantener B y muestreo de 50 FE al comparar. El origen elegido penaliza el arranque; comparar campañas con otra definición requiere recalcularla.
