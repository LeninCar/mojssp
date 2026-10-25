# Entrega y estado de autorización

No se ejecutaron optimizaciones nuevas. El holdout sigue cerrado.

- [Lista exacta propuesta: siete bases, perfiles, HV y 21 ternas por semilla](PROPUESTA_PILOTO_PARA_APROBACION.md).
- [Informe y límites de la recomendación](INFORME.md).
- [Contribuciones por ejecución y brazo](tables/individual_contributions.csv).
- [Recomendaciones y standalone](tables/recommendations.csv).
- [Estabilidad entre semillas](tables/stability.csv).
- [Contribuciones nulas](tables/zero_contributions.csv); [empates/incertidumbre](tables/ties_or_uncertain.csv) (tabla vacía con cabecera).
- [Discrepancias con standalone](tables/standalone_disagreements.csv).
- [Inventario de datos faltantes](tables/missing_data.csv).
- [Auditoría final](evidence/final_audit.json), [fuentes preservadas](tables/source_preservation.csv), [pruebas](evidence/tests.txt).
- runs/: 18 informes JSON, con frente y schedules asociados.

## Figuras definitivas revisadas

Estas revisiones ajustan únicamente leyenda y contraste. Los PNG preliminares
se conservaron sin sobrescribir y no son las figuras de presentación.

![Contribuciones por brazo, instancia y semilla](figures/contributions_validated.png)

Desarrollo: seis bases × tres semillas, UCB escalado a 3000 FE. Eje vertical:
MC de HV normalizado; horizontal: semilla. Fuente: JSON scaled originales y
tables/individual_contributions.csv; referencia (1.1,1.1,1.1).

![Mayor contribuyente final](figures/recommendations_validated.png)

Mismas condiciones; los colores identifican brazos. La recomendación cambia entre
semillas en las seis bases. No equivale al mejor standalone ni demuestra cooperación.

## Decisión solicitada

Ya se responde la pregunta de variación con seis bases y 18 ejecuciones existentes,
a coste cero FE. Si se desea añadir el caso histórico de victoria standalone de
SPEA2, la extensión mínima cuesta 9000 FE (solo atribución, comparación histórica
descriptiva). La extensión con standalones actuales pareados cuesta 36000 FE.
No se aprueba ni se ejecuta automáticamente ninguna de estas alternativas.
