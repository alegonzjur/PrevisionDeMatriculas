# Fase 3: líneas base y evaluación de origen móvil

Rama: `fase-3-lineas-base`. Notebook: `notebooks/03_lineas_base.ipynb`. Pipeline: `python -m prevision.pipeline`.
Decisiones y su motivo: `docs/decisiones.md`.

## Objetivo

Fijar el suelo que tendrán que superar los modelos de la fase 4 y el marco con el que se medirán:

1. Un marco de evaluación de origen móvil: cada origen `t` entrena con los cursos hasta `t` y prevé `t+1`.
2. Tres líneas base: ingenuo (último valor), ingenuo con deriva y media móvil.
3. Métricas MAE, WAPE y MAPE (y sesgo), por curso objetivo y en total, con y sin el curso provisional.

No se entrena ningún otro modelo, no se calculan intervalos y no se hace la previsión 2026-27.

## Qué se hizo

### Las líneas base (`prevision.evaluation`)

Cada modelo es una función `historia -> previsión del curso siguiente`, donde `historia` es la matrícula
de la serie hasta el origen (indexada por curso y sin NaN). Los modelos de la fase 4 se enchufan igual.

| Modelo | Previsión |
|---|---|
| `naive` | El último valor |
| `drift` | Último valor más la pendiente media por curso, `(último − primero) / (año último − año primero)`, calculada con **toda** la historia disponible |
| `moving_average` | Media de los últimos 3 cursos (`MA_WINDOW`; con menos cursos, los que haya) |

### Marco de origen móvil (`rolling_origin_forecasts`)

Para cada serie elegible y cada origen `t`: la historia son los cursos con dato hasta `t`, debe tener al
menos `MIN_TRAIN = 4` valores, y el curso `t+1` debe tener dato. La historia se corta por posición antes
de llamar al modelo, así que ningún dato posterior a `t` puede influir. Hay un test que multiplica por 10
todos los datos posteriores a un origen y exige previsiones idénticas.

### Métricas (`compute_metrics`, `metrics_report`)

- **MAE**: error absoluto medio, en estudiantes.
- **WAPE** = suma de |error| / suma de matrícula real. Error relativo del conjunto: pesan más los centros grandes.
- **MAPE** = media de |error| / matrícula real. Error relativo medio por par: todos los centros pesan igual.
- **Sesgo**: error medio con signo (previsión menos real). Negativo = infravalora.
- `*_vs_naive`: métrica del modelo dividida entre la del ingenuo, menos 1. Negativo = mejor que el ingenuo.

Se informa con todos los pares y sin los pares cuyo objetivo es 2025-26 (provisional).

## Resultados

Datos actuales: **761 pares por modelo en 110 series** (objetivos 2019-20 a 2025-26: 107, 107, 108, 109,
110, 110 y 110 pares por curso). De las 112 series elegibles, dos (`Deusto|48012899` y
`Pontificia Comillas|07009045`) tienen exactamente 4 cursos y no dan ningún par.

### Total

| Modelo | MAE | WAPE | MAPE | Sesgo | WAPE frente al ingenuo |
|---|---:|---:|---:|---:|---:|
| Ingenuo | 22,6 | 4,8 % | 5,1 % | −12,6 | |
| **Deriva** | **20,7** | **4,4 %** | **4,7 %** | −5,1 | **−8,3 %** |
| Media móvil | 37,2 | 7,8 % | 8,4 % | −24,1 | +64,3 % |

Sin los pares de 2025-26 el resultado es prácticamente el mismo (651 pares): ingenuo 4,7 %, deriva 4,3 %
(−8,5 %), media móvil 7,7 %. El curso provisional no cambia la conclusión.

### Por curso objetivo (WAPE)

| Curso | Pares | Ingenuo | Deriva | Media móvil |
|---|---:|---:|---:|---:|
| 2019-20 | 107 | 4,0 % | 3,7 % | 6,5 % |
| 2020-21 | 107 | 4,3 % | 4,3 % | 6,9 % |
| 2021-22 | 108 | 4,3 % | 3,9 % | 6,6 % |
| 2022-23 | 109 | 5,4 % | 5,0 % | 8,3 % |
| 2023-24 | 110 | 4,9 % | 4,7 % | 8,4 % |
| 2024-25 | 110 | 5,3 % | 4,3 % | 9,1 % |
| 2025-26 (provisional) | 110 | 4,9 % | 4,5 % | 8,6 % |

La deriva es mejor o igual que el ingenuo en los siete cursos (empate en 2020-21). La media móvil es peor en todos.

### ¿Lo sostienen muchos centros o unos pocos?

| | Deriva | Media móvil |
|---|---:|---:|
| Pares con menos error que el ingenuo | 48,6 % | 27,1 % |
| Series con menor MAE que el ingenuo | 43 de 110 | 13 de 110 |

**La mejora de la deriva es agregada y modesta, no general.** En la mitad de los pares gana el ingenuo y
solo en 43 de las 110 series la deriva tiene menos error. El 8 % de mejora del WAPE sale de los centros grandes:

| Tramo de tamaño (terciles de `size_last`) | Pares | WAPE ingenuo | WAPE deriva | Deriva frente al ingenuo |
|---|---:|---:|---:|---:|
| Grande | 294 | 5,5 % | 4,6 % | −16,9 % |
| Mediano | 298 | 3,6 % | 3,9 % | +8,3 % |
| Pequeño | 169 | 4,1 % | 4,6 % | +10,2 % |

En los centros medianos y pequeños, la deriva es **peor** que el ingenuo.

### Sesgo

Las tres líneas base **infravaloran** de media (el ingenuo, 12,6 estudiantes por par; la media móvil, 24,1),
salvo en los centros pequeños, donde el sesgo es ligeramente positivo. El periodo tiene crecimiento sostenido
(45 715 matriculados en 2015-16 y 58 956 en 2025-26, +29 %): quien prevé "como el pasado" se queda corto.
La media móvil lo sufre más porque promedia cursos antiguos y más bajos.

## Qué significa para la fase 4

- El listón real es **WAPE 4,4 %** (deriva) en el agregado y **4,8 %** (ingenuo) como suelo; en centros
  medianos y pequeños el listón es el ingenuo (3,6 % y 4,1 %).
- Un modelo que no mejore estas cifras no aporta, y eso es un resultado válido y se documenta.
- Con diferencias de décimas de punto entre modelos, la fase 4 debe mirar también por tramos de tamaño y
  por serie, no solo el agregado.

## Límites y errores reales

- **Sesgo de supervivencia.** Solo se evalúan las 112 series elegibles, que llegan a 2025-26. Los centros
  que cierran no están en la evaluación: prever un cierre queda fuera de alcance, y los errores reales
  sobre "todos los centros" serían algo peores.
- **Los enlaces de centros se decidieron con todo el historial.** Una serie enlazada "sabe" hoy una
  sucesión que en el origen aún no era visible. Afecta a 13 series; es información del futuro en la
  definición de la serie, no en los datos.
- **2025-26 es provisional** y puede revisarse: sus pares se miden contra un dato que puede cambiar.
- **Los pares no son independientes.** Las 761 observaciones salen de 110 series, y una serie aporta hasta
  7 pares correlacionados entre sí. Las diferencias de décimas de punto entre modelos **no se han contrastado
  estadísticamente**: no hay intervalo de confianza ni test. Los 761 pares dan la sensación de más
  potencia de la que hay.
- **Pocos orígenes.** Con `MIN_TRAIN = 4` y 11 cursos, cada serie tiene como máximo 7 orígenes, todos en
  un periodo de crecimiento. No se sabe cómo se comportarían las líneas base (la deriva en particular, que
  extrapola la tendencia) si la demanda cambiara de signo.
- **La deriva usa toda la historia.** No hay ventana: una serie con un salto antiguo mantiene su efecto en
  la pendiente. No se ha probado con ventana.
- **Los tramos de tamaño usan un dato de 2025-26** (`size_last`) para agrupar, no para prever. Es
  descriptivo.
- **Dos series elegibles no se evalúan** (exactamente 4 cursos).

## Cómo reproducirlo

```bash
conda activate prev-mat
python -m prevision.pipeline   # data/processed/: baseline_forecasts.csv y baseline_metrics.csv, además de lo anterior
pytest
```
