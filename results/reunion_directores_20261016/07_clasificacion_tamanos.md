# Clasificación reproducible del tamaño

Se usan categorías **descriptivas del diseño experimental de ocho geometrías**, no una taxonomía universal del JSSP. Las geometrías de referencia son 5×5, 10×10, 20×10, 10×20, 20×20, 30×20, 40×20 y 50×50, con N=[25,100,200,200,400,600,800,2500]. Se calculan los terciles empíricos con interpolación lineal (NumPy/Pandas): Q₁/₃=200 y Q₂/₃=533.333.

| Categoría de este informe | Regla | Geometrías observadas de referencia | Bases de confirmación |
|---|---|---|---|
| Pequeña | N≤200 | 5×5, 10×10, 20×10, 10×20 | 4 |
| Mediana | 200<N≤533.333 | 20×20 | 1 |
| Grande | N>533.333 | 30×20, 40×20, 50×50 | 3 |

Se conservan juntos los dos diseños de 200 operaciones. Eso produce grupos desbalanceados; no se fuerzan cortes para obtener un ganador determinado. Los archivos archivados mayores también se etiquetan por esta regla, pero “grande” cubre desde 600 hasta 22500 operaciones: para describirlos se deben mirar N y geometría exactos. La columna del CSV es `geometry_category`.

La relación J/M y las dos dimensiones se conservan separadas: 20×10 y 10×20 tienen N=200 pero distinta contención y longitud de cadena. No se reduce toda la estructura a un único número. Las instancias de validación de 2×2, 3×2 y 3×3 no definen los cortes ni entran en inferencia de rendimiento.

La literatura usa familias de benchmarks y dimensiones concretas, sin un umbral único que pueda trasladarse automáticamente a este MO-JSSP con tres objetivos, releases y velocidades. Por eso este informe no etiqueta estos terciles como categorías generales de la literatura. Una comparación con un benchmark externo debe publicar sus propias dimensiones, objetivos, generador y presupuesto.

La categoría mediana tiene una sola base en confirmación. Un intervalo bootstrap idéntico a su valor observado no es precisión perfecta: no hay información para estimar variación entre bases en esa categoría. Se informa como **incertidumbre entre bases no estimable**.

Ver [resultados por tamaño](08_rendimiento_por_tamano.md), [algorithm_by_size](tables/algorithm_by_size.csv) y [registro del criterio](evidence/analysis_audit.json).
