# Referencias y jerarquía de evidencia

La evidencia empírica procede de archivos locales, preservados por SHA-256. Las publicaciones siguientes fundamentan mecanismos; no prueban la eficacia en estas instancias. Se consultaron fuentes primarias o registros de los autores/editoriales. Consulta: 15 de octubre de 2026.

1. Zhang y Li (2007). [MOEA/D: A Multiobjective Evolutionary Algorithm Based on Decomposition](https://doi.org/10.1109/TEVC.2007.892759). Descomposición de objetivos y cooperación entre subproblemas dentro de MOEA/D; distinta de cooperación entre algoritmos del portafolio.
2. Deb, Pratap, Agarwal y Meyarivan (2002). [A fast and elitist multiobjective genetic algorithm: NSGA-II](https://doi.org/10.1109/4235.996017). Ranking, elitismo y crowding. [Registro institucional de los autores](https://research.birmingham.ac.uk/en/publications/a-fast-and-elitist-multi-objective-genetic-algorithm-nsga-ii).
3. Zitzler, Laumanns y Thiele (2001). [SPEA2: Improving the Strength Pareto Evolutionary Algorithm, TIK Report 103](https://sop.tik.ee.ethz.ch/publicationlistfiles/zlt2001a.pdf). Fuerza, densidad y archivo ambiental; sustenta el catálogo, no una garantía de especialización.
4. Li, Fialho, Kwong y Zhang (2014). [Adaptive Operator Selection With Bandits for a Multiobjective Evolutionary Algorithm Based on Decomposition](https://colalab.ai/publications/LiFKZ14.pdf), DOI 10.1109/TEVC.2013.2239648. Ventana, crédito dependiente de escala y selección de operadores. El escalado del repositorio no reproduce FRRMAB, y aquí los brazos son algoritmos completos.

Las fórmulas efectivamente usadas se verifican en código y snapshots, no se sustituyen por las formulaciones de los artículos. El signo de Page-Hinkley se toma de la especificación corregida y `change_detection.py` del repositorio original. Las pruebas y criterios de cierre se distinguen entre el protocolo reciente prospectivo y análisis exploratorios de esta auditoría.

Fuentes locales principales:

- [Campaña reciente y configuración](../portfolio_loop_20261015/manifest.json), [protocolo](../portfolio_loop_20261015/protocol.md), [procedencia corregida](../portfolio_loop_20261015/baseline_execution_provenance.json).
- [Fase 2 piloto](../expanded_portfolio_phase2/pilot/pilot_config.json), [diagnóstico presupuestario](../expanded_portfolio_phase2/budget_diagnostic/budget_config.json).
- Los resultados Fase 1, benchmark, PH y las instancias históricas del repositorio original se identifican mediante rutas absolutas y hashes en [preservación](evidence/preservation_before.json) y tablas con `source_file`. Se consultan sólo en lectura.
- [Dependencias entre campañas](evidence/cross_campaign_audit.json), [errores de recálculo](evidence/analysis_audit.json), [fuentes de figuras](figures/figure_manifest.json).
