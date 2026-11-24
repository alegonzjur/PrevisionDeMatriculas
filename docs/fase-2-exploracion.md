# Fase 2: exploración y calidad de series

Rama: `fase-2-exploracion`. Notebook: `notebooks/02_exploracion.ipynb`. Pipeline: `python -m prevision.pipeline`.
Decisiones y su motivo: `docs/decisiones.md`.

## Objetivo

Antes de modelar hay que saber qué series son fiables. El panel de la fase 1 (144 centros × 11 cursos)
trata como series distintas a los centros que solo cambian de código. Esta fase:

1. Detecta candidatos a sucesión de código de centro con una regla explícita.
2. Aplica solo los enlaces que confirma una persona, guardados en un CSV versionado.
3. Produce un panel de series (`series_id`) con las series enlazadas ya unidas.
4. Mide la calidad de cada serie y marca cuáles son elegibles para prever.

No corrige ni suaviza saltos, no imputa cursos y no entrena ningún modelo.

## Cómo es el panel de entrada

El panel es **rectangular**: 1584 filas = 144 centros × 11 cursos. Un curso sin dato es una fila con
`enrolled = NaN` (no hay ceros ni filas ausentes). Un centro que abre tarde o cierra antes se ve como NaN
al principio o al final. Esto importa porque calcular "primer curso" o "último curso" con `year_start`
da siempre 2015 y 2025: hay que usar solo los cursos con matrícula informada.

Esto se descubrió al ejecutar con datos reales: la primera versión de `detect_candidates` daba **0
candidatos** porque usaba `year_start` de todas las filas. Los tests sintéticos no lo detectaron porque
`make_panel` solo generaba filas con dato. Se corrigió con un test que reproduce el panel rectangular
(`test_nan_padding_rows_do_not_hide_succession`).

## Qué se hizo

### Detección de candidatos (`prevision.linking.detect_candidates`)

Un centro **A** que termina antes del último curso y otro centro **B** de la misma universidad que empieza
el mismo curso en que termina A o el siguiente. No hay umbral automático sobre el tamaño: se muestra
`size_ratio` y decide una persona. `ambiguous` marca los casos con más de un B posible para un A o más de un
A posible para un B.

Resultado con el Excel actual: **22 candidatos, 10 de ellos ambiguos** (los 10 son de País Vasco y de
Católica de Ávila).

### Enlaces confirmados (`data/reference/center_links.csv`)

Columnas `university, from_center_code, to_center_code, decision, note`. `decision` es `sí`, `no` o
`dudoso`; **solo `sí` se aplica**. Los `no` y `dudoso` también se guardan para no volver a preguntar. Se
versiona en git, de modo que cada enlace se revisa en un diff.

Decisiones del autor sobre los 22 candidatos:

- **14 enlaces `sí`**: Barcelona (2, cadena A→B→C), Católica de Ávila, Católica de Valencia, Europea de
  Madrid, Francisco de Vitoria, La Laguna, La Rioja (2, cadena), País Vasco (2), Pompeu Fabra, Salamanca y
  Valladolid.
- **1 `dudoso`**: Internacional de la Empresa (64 → 190, el tamaño se triplica; puede ser un centro nuevo y
  no una sucesión).
- **7 `no`**: la clínica Mompía (Cantabria, 20 matriculados) frente a Católica de Ávila y seis pares de
  País Vasco.

**País Vasco.** Con la decisión de aceptar País Vasco como `sí`, solo se aplican los dos pares con
sentido por nombre y tamaño: Donostia (`20008684`) → Facultad Sección Guipúzcoa (`20009664`, 525 → 499) y
Leioa escuela (`48008744`) → Facultad de Medicina y Enfermería (`48012841`, 687 → 686). Los otros seis
pares quedan `no`. Aplicar los ocho es imposible: Donostia tendría cuatro enlaces de salida y Leioa
aparece a la vez como origen y destino, lo que forma un ciclo (`apply_links` lo rechaza con `ValueError`).
Es un juicio por nombre y tamaño; enlazarlos solo añade el curso 2015-16 a series que ya tienen 10 cursos.

**Enlace manual fuera de los candidatos.** Antonio de Nebrija `28051891` → `28055225` (`sí`). El código
antiguo se extingue poco a poco (524 en 2021-22 → 3 en 2025-26) mientras el nuevo crece (48 → 395), y la
suma queda estable (421, 419, 425 y 398 desde 2022-23). No salía como candidato porque el centro antiguo
sigue activo con 3 alumnos (ver límites). Con él son **15 enlaces `sí`** y 13 series con centros enlazados
(dos de ellas, cadenas de tres centros).

**San Juan de Dios** (Sevilla → Pontificia Comillas) no aparece entre los candidatos porque son
universidades distintas. Sigue como dos series, según la decisión de la fase 1.

### Aplicación de enlaces (`prevision.linking.apply_links`)

`series_id = "{universidad}|{código final}"`, con el código más reciente de la cadena. Si dos centros de
una misma serie coinciden en un curso, se suma la matrícula (`min_count=1`: NaN si todos son NaN),
`pct_women` se pondera por matrícula, `is_provisional` es verdadero si alguno lo es y el nombre es el del
centro más reciente. Se rechazan con `ValueError` los enlaces a centros que no existen en la universidad,
los ciclos y las bifurcaciones (dos enlaces desde el mismo centro).

**Invariante:** la matrícula total por curso no cambia al enlazar (45 715 en 2015-16 y 58 956 en 2025-26,
igual que en la fase 1). Se comprueba en los tests y en cada ejecución del pipeline (`build_series` lanza
`ValueError` si falla).

Resultado: **144 centros → 129 series**.

### Calidad de series (`prevision.quality.series_quality`)

Una fila por serie: primer y último curso con dato, nº de cursos con dato, `active_last` (llega al último
curso), tamaño en el último curso, mayor salto interanual, nº de saltos, si tiene centros enlazados y si es
elegible. Solo cuentan los cursos con matrícula informada y no se compara a través de un curso sin dato,
para no fabricar saltos falsos.

**Elegible = llega al último curso y tiene al menos `MIN_SEASONS` cursos con dato.**

## Umbrales

| Parámetro | Valor | Por qué |
|---|---:|---|
| `MIN_SEASONS` | 4 | Entre las 123 series activas, 11 tienen de 1 a 3 cursos, 2 tienen 4 y el resto 7 o más: el corte natural cae entre 3 y 4. |
| `JUMP_RATIO` | 1,5 | La mediana del mayor salto por serie es 1,10 y el percentil 90 es 2,00. Con 1,5 se marcan 20 series (16 %); con 2,0 serían 12 y con 3,0, 4. |

Son los valores provisionales del diseño: tras mirar las distribuciones no se cambiaron. Son constantes
en `config.py`, así que cambiarlos es editar el valor y regenerar. **`MIN_SEASONS = 4` es un mínimo de
historia, no una garantía de poder evaluar**: la evaluación de origen móvil (fase 3) necesitará más
cursos de entrenamiento y puede exigir un mínimo mayor.

## Resultado

| | Sin enlazar | Con enlaces |
|---|---:|---:|
| Series | 144 | 129 |
| Activas en 2025-26 | 124 | 123 |
| **Elegibles** | **109** | **112** |

Enlazar sube en 3 el número de series elegibles (de 109 a 112): al unir centros, algunas series que
quedaban fuera por poca historia pasan a tener cursos suficientes.

**17 series no elegibles:**

- *No llegan a 2025-26 (6):* Internacional de la Empresa `28055250` (solo 2024-25, el `dudoso`), Málaga
  `29009417` (2015-16, 10 alumnos al final), Europea de Madrid `46035631` (2015-17, 1 al final), Autónoma de
  Barcelona `08044363` (2015-19, 4 al final), València `12003274` (2015-21, 2 al final) y Murcia `30013116`
  (2015-2023, 225 al final).
- *Activas pero con menos de 4 cursos (11):* seis centros que empiezan en 2025-26 (Abat Oliba CEU,
  Alfonso X el Sabio Mare Nostrum, CEU Fernando III, Internacional de la Empresa `28056023`, Miguel
  Hernández de Elche, Vic-Central de Catalunya), dos con 2 cursos (Atlántico Medio, Internacional
  Villanueva) y tres con 3 (Europea Miguel de Cervantes y dos de Loyola Andalucía).

Las series cortas **no se podrán prever con rigor**: quedan fuera del conjunto elegible. Entre las
elegibles, el tamaño en 2025-26 tiene mediana 433 (mínimo 55, máximo 1913).

**Saltos.** 11 de las 112 series elegibles tienen al menos un salto interanual superior a 1,5. No se
corrigen: son crecimiento real de centros que abren grupos o cambios administrativos, y borrarlos sería
inventar datos. Solo se marcan (`max_jump_ratio`, `n_jumps`) para que la fase 3 los tenga presentes.

## Límites y errores reales

- **Los enlaces son un juicio.** Se decidieron mirando fechas, nombres y tamaños. Un enlace falso une dos
  series distintas sin que nada lo delate después; por eso cada uno lleva su nota y el fichero está en git.
- **La regla de detección no encuentra todas las sucesiones.** Solo considera como A los centros que
  terminan antes del último curso. Si el centro antiguo se extingue poco a poco y sigue con unos pocos
  alumnos en 2025-26, no es candidato. Caso real: Antonio de Nebrija `28051891` → `28055225`, que se enlazó
  a mano (ver arriba). Antes de enlazarlo era la única serie elegible con menos de 30 alumnos y su salto
  (×47) era un artefacto. **No se ha buscado de forma sistemática si hay más casos así**; los centros
  con matrícula final muy baja y los saltos grandes son la pista.
- **Otros cierres sin sucesor.** Las series que terminan antes con pocos alumnos (Málaga, Europea de Madrid
  `46035631`, Autónoma de Barcelona, València) parecen colas de planes que se extinguen. Murcia `30013116`
  (225 alumnos en 2022-23, 9 cursos) desaparece sin candidato: no se sabe si es un cierre o un cambio de
  adscripción no detectado.
- **2025-26 es provisional.** Una serie que "termina" ahí o que empieza ahí puede estar incompleta, y el
  último curso de las demás puede revisarse.
- **Elegible no significa fácil de prever.** Es un filtro de historia mínima. No mide si la serie es
  estable (11 elegibles tienen saltos) ni si el tamaño es suficiente para un porcentaje de error con
  sentido.
- **San Juan de Dios** (Sevilla y Comillas) sigue como dos series: el modelo puede confundir la
  transferencia administrativa con tendencia (ver fase 1).

## Cómo reproducirlo

```bash
conda activate prev-mat
python -m prevision.pipeline   # data/processed/: enfermeria_panel.csv, link_candidates.csv,
                               #   enfermeria_series.csv, series_quality.csv, cleaning_log.md
pytest
```

Si falta `data/reference/center_links.csv`, el pipeline no falla: avisa, genera la tabla de candidatos y no
aplica ningún enlace.
