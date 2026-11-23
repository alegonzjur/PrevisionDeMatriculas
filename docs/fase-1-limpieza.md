# Fase 1: carga y limpieza

Rama: `fase-1-limpieza`. Notebook: `notebooks/01_limpieza.ipynb`. Pipeline: `python -m prevision.pipeline`.

## Objetivo

Convertir `data/raw/Matriculados.xlsx` (SIIU) en un **panel limpio por centro**: una fila por centro
(universidad + código de centro) y curso, con los matriculados en *Graduado o Graduada en
Enfermería*. Cada regla de limpieza queda documentada, testeada y registrada con el nº de filas
afectadas.

## Qué hay en el Excel

- Tres filas de título. La **fila 3** lleva el curso (solo sobre la columna *Total* de cada par) y la
  **fila 4** es la cabecera real: columnas fijas y, después, pares *Total / % Mujeres* por curso, del más
  reciente (2025-2026) al más antiguo (2015-2016): 11 cursos.
- Hojas usadas: "Matriculados Global por centro" (base del panel) y "Matriculados Grado" (solo para validar
  totales por universidad).
- La hoja de centros mezcla Grado (7914 filas), Máster (7522) y Doctorado (2338).
- Los códigos son texto con ceros a la izquierda (p. ej. `04008558`) y se conservan como texto.

## Reglas aplicadas

Recuentos del registro `cleaning_log.md`, con el Excel actual (filas del Excel salvo R3):

| Regla | Qué hace | Antes | Después |
|---|---|---:|---:|
| R1 nivel | Se queda con el nivel Grado (fuera Máster y Doctorado) | 17 774 | 7 914 |
| R2 titulación | Solo *Graduado o Graduada en Enfermería*; fuera Diplomado, PCEO/dobles grados, másteres y doctorados | 7 914 | 158 |
| V1 validación | Totales por universidad y curso frente a la hoja "Matriculados Grado" | 770 comparaciones | 0 diferencias |
| R3 unificación | Una serie por (universidad, código de centro); se suman los códigos de titulación | 158 series | 144 centros |

**R2: el texto literal de `CLAUDE.md` no basta.** Muchos centros aparecen como "Graduado o Graduada en
Enfermería por la Universidad de X". El texto exacto solo da 8 filas; el patrón
`^Graduado o Graduada en Enfermería( por .*)?$` da 158 (70 universidades). Entre lo que se excluye están
86 másteres, 16 PCEO, 6 Diplomado y 6 doctorados que mencionan Enfermería.

**R3: por qué se suman los códigos.** Algunas titulaciones cambian de código por cambio de plan y la
serie queda partida. Hay dos situaciones:
- *Sin solape*: Almería, código `2501129` hasta 2020-21 y `2504090` desde 2021-22.
- *Con solape*: el plan antiguo se extingue mientras el nuevo crece. Ejemplo: Europea de Madrid,
  216 → 6 en el plan viejo mientras el nuevo sube de 134 → 549 (2017-18 a 2021-22). Hay 49 celdas
  centro-curso con solape en 13 centros. La suma es lo correcto: son estudiantes distintos de la misma
  titulación en el mismo centro.

La suma usa `min_count=1`: si todos los códigos son `NaN`, el resultado es `NaN`, nunca 0.
El % de mujeres se pondera por matriculados.

**Clave de unificación = (universidad, código de centro).** El nombre del centro puede cambiar con el
mismo código (Melilla pasa de "Facultad de Ciencias de la Salud de Melilla" a "Facultad de Enfermería de
Melilla"). Por eso hay 144 centros y no 145 (que sale al contar por nombre). Como etiqueta se usa el nombre
más reciente con dato.

## Validación

La suma de matriculados por universidad y curso del panel de centros coincide con la de la hoja
"Matriculados Grado" (0 diferencias en 770 comparaciones). Límite: es una comprobación de que no se
pierden ni se duplican filas al agrupar. Como ambas hojas parten de las mismas titulaciones, **no detecta
errores del propio SIIU**.

Total nacional del panel: 45 715 (2015-16) → 58 956 (2025-26, provisional).

## Caso especial: San Juan de Dios (Sevilla) y Pontificia Comillas

El *Centro de Enfermería San Juan de Dios* (Univ. Sevilla, `41015500`) pasa a la *EUEF San Juan de Dios*
(Univ. Pontificia Comillas, `28042772`). **Decisión del autor: se dejan como dos series separadas.**
Los datos muestran una transferencia progresiva, no un corte limpio:

| Curso | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 |
|---|---:|---:|---:|---:|---:|
| Sevilla | 314 | 330 | 159 | 87 | 67 |
| Comillas | 499 | 635 | 745 | 949 | 1195 |

Consecuencia: la serie de Sevilla cae y la de Comillas sube por un efecto administrativo, no por un
cambio de la demanda. Un modelo que trate cada serie por separado puede confundirlo con tendencia.
Conviene tenerlo presente al modelar (fase 4) y, si se prefiere, revisar entonces la decisión de unirlas.

## Límites y errores reales

- **2025-26 es provisional** (avance) y puede revisarse. Va marcado en `is_provisional`: se marca siempre el último curso del fichero, de modo que sigue siendo correcto al añadir cursos nuevos.
- **Series cortas y con huecos.** El panel tiene 1 584 filas (144 centros × 11 cursos), de las que 325 son
  `NaN` (sin dato ese curso). Solo 95 centros tienen los 11 cursos con dato; 49 tienen menos, y **12 centros
  tienen un solo curso con dato**. La fase 2 debe decidir qué centros entran en el modelo.
- **Centros que desaparecen o aparecen.** Por ejemplo, Europea de Madrid (`28051852`) no tiene dato en
  2024-25 ni 2025-26. No se han tratado como cierre ni apertura: solo se marcan como `NaN`.
- **No se ha verificado** si los centros con un solo curso son centros nuevos, cierres o errores de código.
- `Egresados.xlsx` queda fuera, según lo decidido.

## Cómo reproducirlo y cómo actualizar los datos

```bash
conda activate prev-mat
pip install -e ".[notebooks]"        # una vez
python -m prevision.pipeline         # genera data/processed/enfermeria_panel.csv y cleaning_log.md
pytest                               # 37 tests (incluye ejecutar el notebook)
```

Para actualizar con datos nuevos: sustituir `data/raw/Matriculados.xlsx` (que el programa nunca modifica) y
ejecutar `python -m prevision.pipeline`. Si los totales por universidad dejan de cuadrar con la hoja de
Grado, el pipeline lanza un aviso con las diferencias. El notebook sirve de constancia de los pasos y llama
a las mismas funciones que el pipeline; al final comprueba que dan el mismo panel.

`data/processed/` no se versiona (se regenera con un comando). DVC llegará en la fase 5.

## Estructura del código

- `src/prevision/config.py`: rutas, hojas, patrón de titulación y mapa de columnas.
- `src/prevision/loading.py`: `read_raw_sheet`, `wide_to_long`.
- `src/prevision/cleaning.py`: `CleaningLog`, `filter_nursing_degrees`, `unify_center_series`.
- `src/prevision/validation.py`: `compare_university_totals`.
- `src/prevision/pipeline.py`: `extract`, `transform`, `load`, `run_pipeline`.
- `tests/`: un fichero por módulo, más `test_notebook.py`.
