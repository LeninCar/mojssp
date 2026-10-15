# Reproducción de la auditoría

Todos los scripts confinan escrituras a su directorio padre de reunión. Los datos originales son sólo lectura. No inicializan algoritmos ni ejecutan búsqueda. La primera captura `preserve.py` se niega a sobrescribir `preservation_before.json`.

Orden:

1. `preserve.py` con Python bundled (ya capturado; no sobrescribir).
2. `discover.py` con Python bundled: inventario de esquemas/configuración histórica.
3. `analyze.py` con Python bundled: inventario, características, tablas, HV/AUC/MC y estadística principal (NumPy/Pandas). Cambia sólo tablas derivadas.
4. `supplement.py` con Python existente con SciPy: contrastes exploratorios, dependencias e inspección independiente de características.
5. `plot.py` con Python existente con matplotlib: 23 figuras PNG/SVG desde tablas procesadas.
6. `report.py` con Python bundled: documentos y capítulos del informe.
7. `verify.py` con Python bundled: conservación, trazabilidad, enlaces y manifest final.

Python bundled: `C:/Users/lenin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. El Python 3.12 existente del sistema dispone de matplotlib/SciPy, que no están en el bundle. No se instalaron ni modificaron dependencias. Semilla de análisis 20261016; 20000 remuestreos bootstrap de bases. Las variaciones mínimas de IC frente al informe previo responden a la semilla analítica, no a cambios en datos.

Para una reproducción externa se requieren los archivos del manifest en las mismas ubicaciones o adaptar explícitamente ROOT/ORIGINAL en una copia de estos scripts. No interpretar un commit histórico como captura exacta de un árbol sucio. No interpretar CSV del test ni abrir sus instancias para hipótesis.

## Ampliaciones de la sesión

Después de `analyze.py` y `supplement.py`, ejecutar `catalog.py` para completar metadatos, etapas y AUC histórica. `late_campaigns.py` captura fuentes externas una sola vez: se niega a refrescar el corte P7 existente. Tras `report.py`, ejecutar `appendix.py` para incorporar esa instantánea y la incidencia externa; finalmente `verify.py`. La captura de P7 nunca ejecuta ni espera el runner.
