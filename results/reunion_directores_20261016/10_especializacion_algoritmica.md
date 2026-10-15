# ¿Existe evidencia de especialización algorítmica?

**No hay evidencia suficiente para afirmar una regla general que asigne un algoritmo a un tipo o tamaño de instancia. Sí hay heterogeneidad y señales locales que justifican investigar esa posibilidad.**

Se observan excepciones claras a una superioridad uniforme de MOEA/D: SPEA2 y NSGA-II lo superan en la base 5×5 de confirmación, y existen victorias históricas a 1000 FE. También hay evidencia exploratoria de sensibilidad relativa al cuello de botella: el contraste emparejado de NSGA-II es positivo en 8/8 bases históricas, pero la familia de ocho pruebas corregidas no supera el umbral del 5%. No significa que el efecto sea inexistente; la precisión y el diseño todavía limitan la generalización.

| Propiedad | Qué permiten los datos | Qué falta |
|---|---|---|
| Ganador de una base | Comparación de medias y dispersión de semillas a igual FE | Replicar la generación de bases con la misma característica |
| Tamaño | Asociaciones por N y geometría exacta | Varias bases por tamaño con perfiles cruzados |
| Carga | Contrastes relativos de tratamiento histórico | Nueva confirmación dirigida e independiente |
| Holgura/energía | Sensibilidad al perfil y correlaciones | Cotas comparables, efectos físicos y diseño cruzado |
| Modos | Descripción de cinco modos | Corridas existentes con cantidades variables; no están en cohortes principales |
| Generalización | Confirmación interna del escalado | Test final sin abrir y familias externas |

Para resolverlo, conviene acordar antes de usar el test una hipótesis acotada, por ejemplo “el cuello de botella cambia la ventaja NSGA-II frente a MOEA/D”. Se necesitan bases independientes replicadas en varias geometrías, tratamiento emparejado con la misma ruta/duraciones base, semillas comunes y un único presupuesto principal. El número de bases debe justificarse mediante precisión o potencia con el efecto piloto y un mínimo relevante, no sólo aumentando semillas.

La evaluación debe agrupar por base y probar la interacción algoritmo×tratamiento. Un clasificador multivariable entrenado con ocho bases por campaña sería frágil. Si se usan modelos predictivos, separar por familias/base al validar y mantener el holdout final intacto. La auditoría y el diseño se pueden discutir antes de la reunión; las nuevas optimizaciones deben quedar para después de acordar el protocolo.

La complementariedad regional de frentes tampoco equivale a especialización por instancia. Dos algoritmos pueden producir soluciones diferentes de una misma base sin que uno sea el mejor método para una familia entera.

Evidencia: [tamaño](08_rendimiento_por_tamano.md), [características](09_rendimiento_por_caracteristicas.md), [contrastes de perfiles](tables/profile_relative_effects.csv).
