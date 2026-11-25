# Fase 4: modelos globales de aprendizaje automático

Rama: `fase-4-modelos`. Notebook: `notebooks/04_modelos.ipynb`. Pipeline: `python -m prevision.pipeline`.
Decisiones y su motivo: `docs/decisiones.md`.

## Objetivo

Responder a una pregunta: **¿un modelo global de aprendizaje automático supera a la deriva y al ingenuo en la
evaluación de origen móvil, y dónde?** Un "no" documentado es un resultado válido.

Se evalúan dos modelos con las mismas variables y el mismo marco que las líneas base de la fase 3:

- **Ridge** (`ridge`): regresión lineal regularizada, como control honesto. Si el gradient boosting no le gana,
  la no linealidad no aporta.
- **Gradient boosting** (`gbm`): `HistGradientBoostingRegressor` de scikit-learn.

No se hacen modelos por serie (ETS/ARIMA), modelos preentrenados, intervalos de predicción ni la previsión
2026-27. Tampoco MLflow ni el resto de MLOps (fase 5).

## Veredicto

Criterio declarado **antes de ver resultados**: un modelo gana si su WAPE total es menor que el de la deriva
**y** no es peor que el ingenuo en los tramos mediano y pequeño.

**Ningún modelo supera el listón.**

| | WAPE total (761 pares) | ¿< deriva (4,30 %)? | Mediano frente al ingenuo | Pequeño frente al ingenuo | ¿Gana? |
|---|---:|:---:|---:|---:|:---:|
| `gbm` | 4,04 % | sí | −6,1 % (mejor) | **+30,5 % (peor)** | **no** |
| `ridge` | 4,22 % | sí, por 0,08 puntos | **+3,5 % (peor)** | **+18,4 % (peor)** | **no** |

Lo que sí hay es una mejora agregada modesta que sostienen los centros grandes. En los centros pequeños el
ingenuo sigue siendo el mejor modelo, y los dos modelos globales lo empeoran con más claridad que la deriva.

## Qué se hizo

### Marco global (`prevision.evaluation.rolling_origin_global`)

Un modelo global no recibe una serie, sino todas. En cada origen `t`:

1. Se construyen los ejemplos de entrenamiento: todos los pares (serie, origen `o`) con `o + 1 <= t`, es decir,
   lo que ya es conocido en `t` (`build_examples(series, up_to=t)`).
2. Se ajusta el modelo y se prevé `t + 1` para cada serie.

Los pares son **exactamente los mismos** que los de las líneas base (761 pares en 110 series, mismo `MIN_TRAIN`).
Si un par no se puede prever, se lanza un error: no se rellena con otro modelo. Si el origen tiene menos de
`MIN_TRAIN_EXAMPLES = 30` ejemplos, también es un error.

El modelo predice el **crecimiento logarítmico** `ln(y[t+1] / y[t])` y la previsión es
`y[t] · exp(predicción)`. Así los centros de distinto tamaño son comparables y el modelo parte del ingenuo
(crecimiento 0).

### Variables (`prevision.features`)

Todas se calculan solo con cursos con dato hasta el origen. Antes de calcular nada, la tabla se recorta al
último curso visible, de modo que ninguna variable, ni las medias entre series, puede ver el futuro.

| Variable | Qué es |
|---|---|
| `g1`, `g2` | Crecimientos logarítmicos de los dos últimos cursos |
| `drift_rel` | Pendiente media de toda la historia dividida entre el último valor |
| `log_size` | Logaritmo del último valor |
| `n_seasons` | Número de cursos con dato |
| `pct_women` | % de mujeres del último curso |
| `system_growth` | Crecimiento logarítmico medio de las demás series en el último curso |
| `region_growth` | Lo mismo, solo con las demás series de la misma comunidad (vacío si hay menos de 2) |

La versión **principal** (`base`) usa las siete primeras. No hay identificador de universidad ni de centro: con
tantas series y tan pocos ejemplos dejaría al modelo memorizar series.

### Hiperparámetros

Fijados de antemano en `config.py`, conservadores, y **nunca ajustados con los pares de evaluación**:

- `RIDGE_ALPHA = 10.0`. Ridge con imputación por la mediana y estandarización dentro del entrenamiento.
- `GBM_PARAMS`: `max_iter = 100`, `learning_rate = 0.05`, `max_depth = 3`, `min_samples_leaf = 20`,
  `l2_regularization = 1.0`, `random_state = 0`.

### Tests

Los de no-fuga multiplican por 10 todos los datos posteriores a un origen y exigen previsiones idénticas
(variables, medias entre series y ajuste incluidos). Se comprobó que el test **falla** si se elimina el recorte
temporal. Además: ningún ejemplo de entrenamiento tiene objetivo posterior al origen; los pares son los de las
líneas base; un modelo de crecimiento cero reproduce el ingenuo; dos ejecuciones dan lo mismo.

## Resultados

Cifras de `data/processed/model_metrics.csv`, idénticas a las del notebook (la última celda lo comprueba).

### Total

| Modelo | MAE | WAPE | MAPE | Sesgo | WAPE frente al ingenuo |
|---|---:|---:|---:|---:|---:|
| Ingenuo | 22,5 | 4,71 % | 5,03 % | −12,4 | |
| Deriva | 20,5 | 4,30 % | 4,71 % | −4,8 | −8,7 % |
| `ridge` | 20,1 | 4,22 % | 4,58 % | −5,8 | −10,4 % |
| `gbm` | 19,2 | **4,04 %** | 4,61 % | +0,3 | **−14,4 %** |

Sin los pares de 2025-26 (provisional, 651 pares): ingenuo 4,67 %, deriva 4,25 % (−9,1 %), `ridge` 4,34 %
(−7,2 %), `gbm` 4,07 % (−13,0 %). **Sin el curso provisional, `ridge` es peor que la deriva.** Su ventaja total
sobre la deriva (0,08 puntos) depende de un único curso que puede revisarse.

El sesgo de `gbm` es casi nulo y el de `ridge` sigue siendo negativo (infravalora). Las líneas base infravaloran
porque el periodo es de crecimiento sostenido y quien prevé "como el pasado" se queda corto.

### Por curso objetivo (WAPE)

| Curso | Pares | Ingenuo | Deriva | `ridge` | `gbm` |
|---|---:|---:|---:|---:|---:|
| 2019-20 | 107 | 4,06 % | 3,70 % | **6,48 %** | 3,93 % |
| 2020-21 | 107 | 4,28 % | 4,29 % | 4,34 % | 3,96 % |
| 2021-22 | 108 | 4,31 % | 3,84 % | 3,67 % | 3,40 % |
| 2022-23 | 109 | 5,40 % | 5,02 % | 4,69 % | 5,14 % |
| 2023-24 | 110 | 4,93 % | 4,67 % | 3,73 % | 4,02 % |
| 2024-25 | 110 | 4,97 % | 3,94 % | 3,34 % | 3,92 % |
| 2025-26 (provisional) | 110 | 4,92 % | 4,59 % | 3,60 % | 3,87 % |

- `gbm` mejora al ingenuo en los siete cursos y a la deriva en cinco (en 2024-25 por solo 0,02 puntos).
- `ridge` empeora al ingenuo en 2019-20 (+60 %) y 2020-21, con 107 ejemplos de entrenamiento en el primer
  origen. Su resultado total mezcla un arranque malo con un tramo final bueno.

### ¿Lo sostienen muchos centros o unos pocos?

| | Deriva | `ridge` | `gbm` |
|---|---:|---:|---:|
| Pares con menos error que el ingenuo | 48,9 % | 46,3 % | 48,5 % |
| Series con menor MAE que el ingenuo | 44 de 110 | 39 de 110 | 48 de 110 |
| Comunidades con menor WAPE que el ingenuo | 8 de 17 | 7 de 17 | 9 de 17 |

**La mejora es agregada y modesta, no general.** En más de la mitad de los pares gana el ingenuo.

### Por tamaño de centro (WAPE)

| Tramo | Pares | Ingenuo | Deriva | `ridge` | `gbm` |
|---|---:|---:|---:|---:|---:|
| Grande | 294 | 5,41 % | 4,46 % (−17,6 %) | 4,35 % (−19,6 %) | **4,13 % (−23,8 %)** |
| Mediano | 291 | 3,65 % | 3,95 % (+8,5 %) | 3,77 % (+3,5 %) | **3,43 % (−6,1 %)** |
| Pequeño | 176 | **4,04 %** | 4,43 % (+9,8 %) | 4,78 % (+18,4 %) | 5,27 % (+30,5 %) |

Entre paréntesis, el WAPE frente al ingenuo. `gbm` mejora en grandes y medianos y es claramente peor en los
pequeños, tanto en WAPE como en sesgo (+6,3 estudiantes por par, que sobreestima).

### Solo cursos objetivo desde 2021

Subconjunto descriptivo con varias cohortes de entrenamiento (547 pares). Se fijó el corte antes de ver
resultados.

| | Ingenuo | Deriva | `ridge` | `gbm` |
|---|---:|---:|---:|---:|
| Total | 4,91 % | 4,41 % | **3,80 %** | 4,07 % |
| Grande | 5,75 % | 4,71 % | 3,81 % | 4,32 % |
| Mediano | 3,48 % | 3,77 % | 3,30 % | 3,15 % |
| Pequeño | **4,38 %** | 4,64 % | 5,14 % | 5,26 % |

Aquí `ridge` sale mejor que `gbm` en el total, pero ambos siguen siendo peores que el ingenuo en los centros
pequeños.

### Sensibilidad (no entra en el veredicto)

La versión principal es `base`. Las variantes añaden el crecimiento medio de la comunidad (`*_region`) o quitan
el de todas las series (`*_no_system`). **El aporte de `system_growth` se vio después de ver los resultados de la
versión `base`.** Elegir la variante por sus pares de evaluación sería ajustar con los datos de evaluación; por
eso `base` sigue siendo la versión principal aunque otra salga mejor.

| Modelo | WAPE total | WAPE desde 2021 |
|---|---:|---:|
| `gbm` (principal) | 4,04 % | 4,07 % |
| `gbm_region` | 4,06 % | 4,06 % |
| `gbm_no_system` | 3,92 % | 3,90 % |
| `ridge` (principal) | 4,22 % | 3,80 % |
| `ridge_region` | 4,02 % | 3,83 % |
| `ridge_no_system` | 3,86 % | 3,79 % |

- Quitar `system_growth` mejora el WAPE total de los dos modelos (−0,12 y −0,36 puntos). El diagnóstico previo
  ya anticipaba que no era informativa (correlación −0,09 con el crecimiento siguiente).
- Añadir el crecimiento de la comunidad no mejora a `gbm` y mejora a `ridge` solo en el total. El diagnóstico
  previo daba +0,03.
- Las variantes no se han medido por tramos de tamaño, así que no se sabe si alguna resuelve el problema de
  los centros pequeños.

Una versión sin `system_growth` sería un candidato legítimo, pero habría que **validarla con datos nuevos** y no
con estos pares.

### Error por comunidad autónoma

Solo descriptivo: de 7 a 119 pares por comunidad, sin muestra para concluir nada. Los modelos tienen menos
error que el ingenuo en 7 (`ridge`) o 9 (`gbm`) de las 17 comunidades. El detalle está en el notebook.

## Qué significa para la fase 5

- El resultado real es un **no matizado**: ningún modelo global supera el listón declarado. Hay una mejora
  agregada de 0,08 (`ridge`) a 0,26 puntos (`gbm`) de WAPE sobre la deriva, sostenida por centros grandes y
  medianos.
- Si se quiere llevar un modelo a la fase 5 (seguimiento, reentrenamiento, aplicación), el candidato natural es
  `gbm` `base`: es más estable entre cursos que `ridge` y el único que mejora al ingenuo en grandes y medianos. Hay que
  llevarlo sabiendo que en centros pequeños el ingenuo gana. Es una decisión del autor, no una conclusión de
  la fase.
- Para los centros pequeños, la previsión por defecto debería seguir siendo el ingenuo. Una regla por tamaño
  (modelo en centros grandes y medianos, ingenuo en pequeños) es una **hipótesis** que usaría el tramo de
  tamaño, definido con un dato de 2025-26, y que no se ha probado en esta fase.
- Con diferencias de décimas de punto, cualquier nueva decisión debería apoyarse en más cursos o en un
  contraste, no en estos 761 pares.

## Límites y errores reales

- **Las diferencias pequeñas no están contrastadas.** Los 761 pares salen de 110 series y una serie aporta hasta
  7 pares correlacionados. No hay intervalo de confianza ni test. La ventaja de `ridge` sobre la deriva (0,08
  puntos) es indistinguible de cero y desaparece sin 2025-26.
- **Pocos orígenes, todos en crecimiento.** Hay como máximo 7 orígenes por serie en un periodo de demanda al
  alza (+29 % de 2015-16 a 2025-26). No se sabe cómo se comportarían los modelos si el signo cambiara. `gbm`
  tiene sesgo casi nulo en este periodo, pero eso puede deberse a que ha aprendido el crecimiento medio.
- **Los primeros orígenes entrenan con poco.** En el origen 2018 hay 107 ejemplos (uno por serie) y en 2024, 761.
  `ridge` rinde peor que el ingenuo justo en esos primeros cursos objetivo.
- **Hiperparámetros fijados a priori y no optimizados.** Es lo honesto, pero puede que otros valores den
  mejor resultado. Cualquier ajuste posterior se rotula como sensibilidad.
- **La versión principal se declaró antes, pero `system_growth` se evaluó después.** Su aporte se vio tras los
  resultados; la decisión de mantener `base` es consciente.
- **El listón incluye el enlace de Murcia** (WAPE ingenuo 4,71 %, deriva 4,30 %), decidido al empezar la fase
  con el historial completo. Los enlaces se decidieron con todo el historial: una serie enlazada "sabe" hoy una
  sucesión que en el origen aún no era visible (afecta a 14 series).
- **Sesgo de supervivencia.** Solo se evalúan las 112 series elegibles, que llegan a 2025-26. No se prevén
  cierres y los errores reales sobre "todos los centros" serían algo peores. Dos series elegibles tienen
  exactamente 4 cursos y no dan pares.
- **2025-26 es provisional.** Sus pares se miden contra un dato que puede revisarse, y el veredicto de `ridge`
  depende de él.
- **El tramo de tamaño usa un dato de 2025-26** (`size_last`) para agrupar y los terciles se calculan con todas
  las series de la tabla de calidad. Es descriptivo, no un criterio de previsión.
- **La región es la CCAA del Excel** y el diagnóstico previo sobre su utilidad fue solo lineal. El error por
  comunidad es descriptivo: sin muestra suficiente por región.
- **Sin identificador de centro.** Un modelo global no puede aprender particularidades de un centro (cambios de
  plazas, cierres de grupo), y esa es una razón plausible de su mal resultado en los centros pequeños, que no
  se ha comprobado.

## Cómo reproducirlo

```bash
conda activate prev-mat
python -m prevision.pipeline   # data/processed/: model_forecasts.csv y model_metrics.csv, además de lo anterior
pytest
```
