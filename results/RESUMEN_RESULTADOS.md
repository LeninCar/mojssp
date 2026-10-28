# Resumen de resultados finales

Estado al 28 de octubre de 2026. HV normalizado con cotas fijas por instancia y
referencia (1,1; 1,1; 1,1). Las medias se calculan por instancia sobre las
semillas y luego con igual peso para cada instancia. Los intervalos son bootstrap
del 95 %; "agrupado" significa remuestreo por instancia base.

## 1. Holdout del PS-MB (resultado principal)

`experiments/holdout_early_moead_600_20261024/`: 80 instancias reservadas,
5 semillas, 3000 FE, código congelado en `holdout-v2-freeze` (f78076b).

| Método | HV medio |
| --- | --- |
| **PS-MB (early_moead_600)** | **0,9924** |
| Pareja MOEA/D + BLMR, reparto pasivo | 0,9876 |
| BLMR solo (mejor individual) | 0,9789 |
| MOEA/D solo | 0,9766 |
| NSGA-II | 0,9525 |
| SPEA2 | 0,9452 |
| NSGA-II + LS | 0,8419 |
| MOPSO | 0,8322 |

| PS-MB contra | Diferencia | IC 95 % | Gana/pierde | p Holm |
| --- | --- | --- | --- | --- |
| BLMR solo | +0,0136 | [+0,0085; +0,0185] | 63/17 | 8,4e-7 |
| MOEA/D | +0,0158 | [+0,0095; +0,0226] | 47/33 | 0,001 |
| Pareja pasiva | +0,0049 | [+0,0006; +0,0093] | 43/37 | 0,088 |

- La regla fijada antes de correr se cumple: supera a BLMR solo con un IC que excluye el cero y supera en media a los siete controles.
- Con la corrección de Holm, la ventaja sobre la pareja pasiva no es significativa. Su IC agrupado [−0,0008; +0,0114] incluye el cero.
- Ningún individual domina. BLMR es el mejor individual de 5x5 a 20x10 y MOEA/D de 20x20 a 50x50. En las instancias grandes, el PS-MB queda entre 0,001 y 0,008 por debajo de MOEA/D.
- Contra el oráculo (el mejor individual de cada instancia elegido a posteriori, 0,9931), la diferencia es −0,0007 con IC [−0,0053; +0,0043]. Un solo método fijo iguala la elección retrospectiva.

## 2. Validación experta

`expert_validation.json` y `scripts/validation/`.

- El modelo, el HV, la normalización y el conteo de FE (exactamente 3000 por corrida) están verificados de forma independiente.
- El código del holdout es idéntico al congelado, y las 12 corridas reproducidas dan resultados bit a bit iguales.
- No hay fugas del desarrollo al holdout, y todas las semillas están completas.
- A12 emparejado y bootstrap agrupado por base incluidos.

## 3. Métricas secundarias: IGD+ y épsilon

`secondary_metrics.json`.

| Métrica | Primero | PS-MB contra UCB escalado |
| --- | --- | --- |
| HV | PS-MB | empate |
| IGD+ (frente de referencia) | PS-MB | empate |
| Épsilon (frente de referencia) | PS-MB | PS-MB mejor |
| IGD+ (cotas fijas) | MOEA/D | UCB escalado mejor |
| Épsilon (cotas fijas) | MOEA/D | empate |

- El PS-MB supera a BLMR solo con todas las métricas y normalizaciones.
- Con las cotas fijas, que pesan sobre todo la energía, gana MOEA/D. Es un compromiso entre tiempo y energía:

| Método | Faltante makespan | Faltante tardanza | Faltante energía | Soluciones de bajo consumo |
| --- | --- | --- | --- | --- |
| PS-MB | 0,061 | 0,055 | 0,104 | 23,6 % |
| UCB escalado | 0,085 | 0,074 | 0,080 | 34,6 % |
| MOEA/D | 0,183 | 0,162 | 0,031 | 70,5 % |
| BLMR | 0,061 | 0,053 | 0,136 | 16,3 % |

El PS-MB y BLMR son los más fuertes en makespan y tardanza, MOEA/D en energía, y el UCB escalado queda en medio.

## 4. Comparación de políticas en el holdout

`experiments/holdout_policy_comparison_20261025/`: 5 políticas con 4 composiciones con BLMR.

| Puesto | Método | HV medio |
| --- | --- | --- |
| 1 | PS-MB | 0,9924 |
| 2 | MOEA/D + BLMR, UCB escalado | 0,9899 |
| 3 | MOEA/D + BLMR, pasivo | 0,9876 |
| 4 | NSGA-II + BLMR, dinámico | 0,9845 |
| 5 | SPEA2 + BLMR, dinámico | 0,9832 |

- MOEA/D es el mejor compañero de BLMR. UCB escalado y rondas dinámicas son las mejores políticas.
- Uniforme, SW-UCB y Page-Hinkley quedan por debajo de BLMR solo.
- El cuarteto (cuatro brazos) es peor que las parejas: repartir el presupuesto entre demasiados brazos diluye el esfuerzo.
- El PS-MB y el UCB escalado empatan estadísticamente (+0,0025, 40/40).

## 5. Barrido del corte (desarrollo)

`experiments/cut_sweep_development_20261028/`: 120 instancias de desarrollo, 3 semillas, 3240 corridas. No se usa el holdout.

| Método | HV medio |
| --- | --- |
| Corte 900 | 0,9943 |
| **Corte 600 (PS-MB)** | **0,9942** |
| Corte 1200 | 0,9919 |
| Corte 1800 | 0,9917 |
| Corte 300 | 0,9912 |
| UCB escalado | 0,9889 |
| Pareja pasiva | 0,9868 |
| BLMR solo | 0,9801 |
| MOEA/D solo | 0,9786 |

- **El corte de 600 está justificado.** Empata con 900 (+0,0001, IC agrupado [−0,0030; +0,0033]) y supera a los cortes más tempranos y más tardíos.
- La regla adopta un corte por tamaño: 1800 en 5x5, 300 en 10x20 y 20x10, entre 600 y 1200 en el resto. Pero contra el PS-MB solo gana +0,0018 fuera de muestra (IC agrupado [+0,0001; +0,0034]), en 57 de 120 instancias, y cada tamaño se decide con solo 3 bases.
- En desarrollo, el PS-MB supera al UCB escalado: +0,0053, IC agrupado [+0,0012; +0,0097].

## Conclusión

El método principal es el **PS-MB**:

- Es primero en HV en el holdout.
- Supera claramente a todos los individuales.
- Su corte de 600 FE está justificado por el barrido.
- Le gana al UCB escalado en desarrollo y empata con él en el holdout.

El UCB escalado se reporta como alternativa equivalente con más cobertura en energía. El corte por tamaño queda como trabajo futuro: requeriría la fase `confirm` en instancias nuevas.

Límites a declarar:

- La ventaja sobre la pareja pasiva no es significativa con Holm.
- MOEA/D es mejor en energía y en las instancias grandes.
- El estudio usa un único presupuesto (3000 FE).

## Datos

- Cada campaña tiene `interpretacion.txt` o `summary.*`, `by_instance.csv`, `runs.csv` y `compact_runs.jsonl.gz`. Este último guarda la curva de HV, el brazo de cada bloque, el reparto del presupuesto y el frente de cada corrida.
- Las carpetas `runs/` completas solo existen en el computador original y en su respaldo.
