# Control uniforme de MC — entrega

**El máximo contribuyente cambia en 14/18 parejas al igualar oportunidades.**
**No se consumieron FE ni se modificó el portafolio.**

- [Informe completo y respuestas explícitas](INFORME_CONTROL_UNIFORME.md).
- [Índice de tablas, figuras y fuentes](INDICE.md).
- [18 parejas, FE y MC por brazo, ganadores y HV](tables/paired_policies.csv).
- [108 contribuciones individuales](tables/individual_contributions.csv).
- [Estabilidad por base](tables/stability_by_base_arm.csv).
- [Inventario de controles y antecedentes excluidos](tables/control_inventory.csv).
- [Verificaciones exactas de archivos standalone a 1000 FE](tables/standalone_1000_archive_checks.csv).
- [Límites y datos faltantes](tables/limitations_and_missing_data.csv).
- [Certificado final](evidence/final_certificate.json).

| Resultado | UCB escalado | Uniforme, 1000 FE por brazo |
| --- | --- | --- |
| Máximo MC MOEA/D / NSGA-II / SPEA2 | 8 / 7 / 3 | 6 / 6 / 6 |
| MC nulas / 54 | 34 | 6 |
| Corridas con los tres brazos de MC positiva | 0 | 12 |
| Bases con un líder igual en las tres semillas | 0 | 1 |
| Parejas con mayor HV global | 17 | 1 |

Los tres brazos pueden aportar utilidad marginal con oportunidades iguales.
La atribución es condicional a la política y al frente obtenido: no prueba mejor
algoritmo universal ni un efecto causal aislado de FE. Las seis medias de HV por
base favorecen scaled. Uniforme muestra más complementariedad, con márgenes
menores y una recomendación todavía variable en cinco de seis bases.

![Cambio de máximo contribuyente](figures/02_winner_transitions.png)

Fuente: paired_policies.csv, seis bases × tres semillas de desarrollo, 3000 FE
totales por política, referencia HV (1.1,1.1,1.1). Los recuentos no representan
18 bases independientes ni una matriz de acierto.

Hay controles completos para las 18 parejas; no hace falta nueva FE para esta
comparación. Se declara la revisión baseline versus research_v1 y se verifica
su comparabilidad pasiva; los controles históricos de otras bases no se mezclan.

El trabajo queda detenido para revisión. Holdout cerrado; ninguna regla o política
nueva se ha implementado.
