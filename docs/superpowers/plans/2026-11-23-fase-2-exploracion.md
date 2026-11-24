# Fase 2: exploración y calidad de series. Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detectar sucesiones de código de centro, aplicar los enlaces que confirme el usuario, producir un panel de series con `series_id` y medir su calidad y elegibilidad.

**Architecture:** Dos módulos nuevos sobre el panel de la fase 1 (`linking.py`, `quality.py`), un paso nuevo en el pipeline y un CSV versionado con las decisiones del usuario. La fase 1 no se modifica salvo `config.py` y `pipeline.py` (se añaden cosas).

**Tech Stack:** Python 3.11, pandas 3.1, pytest, nbclient (entorno conda `prev-mat`).

**Spec:** `docs/superpowers/specs/2026-11-23-fase-2-exploracion-design.md`

## Global Constraints

- Rama `fase-2-exploracion`; commits en español; terminar cada mensaje con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Documentación y comentarios en español; nombres de variables y funciones en inglés.
- `data/raw/Matriculados.xlsx` no se modifica nunca. `data/processed/` no se versiona; `data/reference/` sí.
- Panel de entrada (fase 1), columnas: `university, center_code, center_name, year_start, season, enrolled, pct_women, is_provisional`. `center_code` es texto (con ceros a la izquierda).
- Sumas con `sum(min_count=1)` (NaN si todos NaN). `pct_women` ponderado por matrícula.
- Fichero de enlaces: `data/reference/center_links.csv`, columnas `university, from_center_code, to_center_code, decision, note`; `decision` ∈ {`sí`, `no`, `dudoso`}; solo `sí` se aplica. Se lee con `dtype=str` y UTF-8.
- `series_id = "{university}|{center_code_final}"`, con el código más reciente de la cadena.
- Parámetros en `config.py`: `MIN_SEASONS = 4` (provisional) y `JUMP_RATIO` (se fija en la tarea 5; valor provisional 1.5).
- Todos los tests deben seguir en verde (hoy 37).

## Review Focus

- Centro cuyo código empieza por ceros (`"01234"`): no debe convertirse en número al leer/escribir `center_links.csv`.
- `center_links.csv` con filas `no`/`dudoso` o vacío (solo cabecera): `apply_links` no falla y no enlaza.
- Enlace A→B donde B ya existía varios cursos antes del fin de A (solape de más de un curso): se suma, no se pierde ninguno.
- Cadena con ciclo (A→B y B→A): error claro, no bucle infinito.
- Serie con NaN en un curso intermedio al calcular saltos: no produce error ni salto falso.

---

### Task 1: Detección de candidatos

**Files:**
- Create: `src/prevision/linking.py`, `tests/test_linking.py`
- Modify: `tests/conftest.py` (añadir ayuda `make_panel`)

**Interfaces:**
- Consumes: panel de la fase 1 (ver Global Constraints).
- Produces:
  - `tests/conftest.py::make_panel(rows: list[tuple[str, str, int, float]]) -> pd.DataFrame` con tuplas `(university, center_code, year_start, enrolled)`; rellena `center_name="Centro {code}"`, `season` como `"{y}-{y+1}"`, `pct_women=70.0`, `is_provisional = year_start == máximo de year_start`.
  - `linking.detect_candidates(panel: pd.DataFrame) -> pd.DataFrame` con columnas `university, from_center_code, from_center_name, to_center_code, to_center_name, from_last_year, to_first_year, from_last_enrolled, to_first_enrolled, size_ratio, ambiguous`.

- [ ] **Step 1: Escribir los tests que fallan** en `tests/test_linking.py`:
  - `test_detects_simple_succession`: A (2015-2020, 100) y B (2021-2025, 110), misma universidad → una fila, `from_center_code="A"`, `to_center_code="B"`, `from_last_year=2020`, `to_first_year=2021`, `size_ratio == 1.1`, `ambiguous == False`.
  - `test_candidate_when_b_starts_same_year_a_ends`: B empieza en 2020 (mismo año que termina A) → es candidato.
  - `test_b_two_years_after_is_not_candidate`: B empieza en 2022 → sin candidatos.
  - `test_other_university_not_candidate`.
  - `test_active_center_has_no_successor`: centro que llega al último curso no genera candidatos como A.
  - `test_ambiguous_flagged`: A con dos B posibles, ambos candidatos con `ambiguous == True`; y B con dos A posibles, igual.
  - `test_no_candidates_returns_empty_frame_with_columns`.
- [ ] **Step 2: Ejecutar** `pytest tests/test_linking.py -v`. Expected: FAIL (`ModuleNotFoundError: prevision.linking`).
- [ ] **Step 3: Implementar `detect_candidates`** en `src/prevision/linking.py`. Resumen por centro (primer y último año, matrícula en ambos extremos, último nombre); último curso global = máximo de `year_start`; candidatos = pares misma universidad, `A.last < ultimo`, `B.first ∈ {A.last, A.last+1}`, `A != B`. `ambiguous` = A tiene más de un B o B tiene más de un A. Ordenado por universidad y `from_last_year`.
- [ ] **Step 4: Ejecutar** `pytest tests/test_linking.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git add tests/conftest.py tests/test_linking.py src/prevision/linking.py` · `feat: detección de candidatos a sucesión de código de centro`.

### Task 2: Lectura y aplicación de enlaces

**Files:**
- Modify: `src/prevision/linking.py`, `tests/test_linking.py`

**Interfaces:**
- Consumes: `make_panel` (tarea 1).
- Produces:
  - `linking.load_links(path: Path) -> pd.DataFrame`: lee el CSV (`dtype=str`, UTF-8); si el fichero no existe devuelve un DataFrame vacío con las columnas del contrato.
  - `linking.apply_links(panel: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame`: devuelve columnas `series_id, university, center_code_final, center_name, year_start, season, enrolled, pct_women, is_provisional, n_centers, n_source_codes` (una fila por serie y curso; `n_centers` = centros sumados ese curso; `n_source_codes` = nº de códigos de centro distintos de la serie, repetido en cada fila).
  - Constante `LINK_COLUMNS` en `linking.py`.

- [ ] **Step 1: Escribir los tests que fallan**:
  - `test_load_links_keeps_leading_zeros` (CSV temporal con `"01234"`).
  - `test_load_links_missing_file_returns_empty_with_columns`.
  - `test_simple_link_merges_into_one_series`: A→B con `sí`; una sola `series_id == "U|B"`, con los cursos de A y B.
  - `test_chain_of_three`: A→B y B→C `sí` → una serie `U|C`.
  - `test_overlap_sums_and_weights_pct_women`: A y B coinciden un curso (100 y 50, pct 80 y 50) → enrolled 150, pct ponderado 70, `n_centers == 2`.
  - `test_total_per_season_is_invariant` (suma de `enrolled` por `year_start` igual antes y después).
  - `test_non_yes_decisions_ignored` (`no`, `dudoso`): cada centro conserva su serie.
  - `test_empty_links_gives_own_series_per_center`.
  - `test_link_to_missing_center_raises` y `test_link_across_universities_raises` (`ValueError`).
  - `test_cycle_raises` (A→B y B→A, `ValueError`).
  - `test_all_nan_overlap_stays_nan`.
  - `test_n_source_codes`: serie A→B→C tiene `n_source_codes == 3`; centro sin enlace, 1.
- [ ] **Step 2: Ejecutar** `pytest tests/test_linking.py -v`. Expected: FAIL (funciones no definidas).
- [ ] **Step 3: Implementar `load_links` y `apply_links`.** Validar cada fila `sí` (existencia y misma universidad); resolver cadenas siguiendo `from→to` hasta el final y detectar ciclos; agrupar por `(series_id, year_start)` con `sum(min_count=1)` y media ponderada para `pct_women` (si el peso total es 0 o NaN, NaN); nombre del centro con `year_start` más reciente de la serie; `is_provisional` = any.
- [ ] **Step 4: Ejecutar** `pytest tests/test_linking.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: lectura y aplicación de enlaces de centros`.

### Task 3: Calidad de series

**Files:**
- Create: `src/prevision/quality.py`, `tests/test_quality.py`
- Modify: `src/prevision/config.py` (añadir `MIN_SEASONS = 4`, `JUMP_RATIO = 1.5`, `LINKS_FILE = PROJECT_ROOT / "data" / "reference" / "center_links.csv"`)

**Interfaces:**
- Consumes: salida de `apply_links` (columnas `series_id, university, center_code_final, center_name, year_start, enrolled, n_centers`).
- Produces: `quality.series_quality(series: pd.DataFrame, min_seasons: int = MIN_SEASONS, jump_ratio: float = JUMP_RATIO) -> pd.DataFrame`, una fila por `series_id`: `series_id, university, center_name, first_year, last_year, n_seasons, active_last, size_last, max_jump_ratio, n_jumps, is_linked, eligible`.

- [ ] **Step 1: Escribir los tests que fallan**:
  - `test_n_seasons_and_years`.
  - `test_eligible_at_min_seasons_boundary` (exactamente `min_seasons` cursos y activa → elegible; uno menos → no).
  - `test_series_ending_before_last_season_not_eligible`.
  - `test_jump_flagged_but_data_untouched` (100→300 con `jump_ratio=1.5`: `n_jumps == 1`, `max_jump_ratio == 3`; la entrada no cambia).
  - `test_drop_counts_as_jump` (200→100 da ratio 2.0 en la dirección que más se aleja de 1, es decir `max(r, 1/r)`).
  - `test_nan_in_middle_creates_no_false_jump`.
  - `test_is_linked_from_n_source_codes`: `is_linked = n_source_codes > 1` (serie con `n_source_codes` 2 → True; con 1 → False).
- [ ] **Step 2: Ejecutar** `pytest tests/test_quality.py -v`. Expected: FAIL.
- [ ] **Step 3: Implementar `series_quality`.** `active_last` = la serie tiene el máximo `year_start` global; `size_last` = matrícula del último curso con dato; saltos = cocientes consecutivos entre cursos adyacentes con dato en ambos (si falta uno, no se compara); `max_jump_ratio` = máximo de `max(r, 1/r)` (NaN si no hay comparaciones); `n_jumps` = nº con ratio > `jump_ratio`; `eligible = active_last and n_seasons >= min_seasons`.
- [ ] **Step 4: Ejecutar** `pytest -v`. Expected: todo PASS.
- [ ] **Step 5: Commit** `feat: calidad y elegibilidad de series`.

### Task 4: Pipeline de series

**Files:**
- Modify: `src/prevision/pipeline.py`, `tests/test_pipeline.py`, `.gitignore` (sin cambios si `data/reference/` no está ignorado; comprobarlo)

**Interfaces:**
- Consumes: `detect_candidates`, `load_links`, `apply_links`, `series_quality`, `run_pipeline`.
- Produces: `pipeline.build_series(panel, links_path: Path = LINKS_FILE, out_dir: Path = PROCESSED_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]` que escribe `link_candidates.csv`, `enfermeria_series.csv` y `series_quality.csv` y devuelve `(candidates, series, quality)`. Si `links_path` no existe, emite `UserWarning` y aplica cero enlaces. `main()` encadena `run_pipeline` + `build_series` e imprime el resumen.

- [ ] **Step 1: Escribir los tests que fallan** (con Excel sintético de `build_workbook` y `tmp_path`): `test_build_series_writes_three_files`; `test_build_series_warns_without_links_file`; `test_build_series_with_confirmed_link_merges_series` (dos centros sucesivos + CSV con `sí` → una serie); `test_total_enrolled_unchanged_by_build_series`.
- [ ] **Step 2: Ejecutar** `pytest tests/test_pipeline.py -v`. Expected: FAIL.
- [ ] **Step 3: Implementar `build_series` y actualizar `main`.** Escritura CSV UTF-8, `index=False`; crear `out_dir` si no existe.
- [ ] **Step 4: Ejecutar** `pytest -v`. Expected: todo PASS.
- [ ] **Step 5: Commit** `feat: paso de series en el pipeline`.

### Task 5: Revisión de candidatos (decisión del usuario, punto de parada)

**Files:**
- Create: `data/reference/center_links.csv` (lo rellena el usuario con ayuda de Claude)

- [ ] **Step 1: Generar** `python -m prevision.pipeline` y leer `data/processed/link_candidates.csv`.
- [ ] **Step 2: Presentar al usuario** la tabla (≈16 pares) con tamaño, años y marca de ambiguo, y una recomendación por fila. Marcar las ambiguas (País Vasco, Internacional de la Empresa) y San Juan de Dios como `dudoso` salvo que el usuario decida otra cosa. **Esperar su decisión**: este paso no se ejecuta sin respuesta.
- [ ] **Step 3: Escribir** `data/reference/center_links.csv` con sus decisiones y notas (UTF-8, cabecera `university,from_center_code,to_center_code,decision,note`).
- [ ] **Step 4: Fijar `JUMP_RATIO` y `MIN_SEASONS`** viendo la distribución de saltos y de longitudes en `series_quality.csv`; proponerlos al usuario y actualizar `config.py` con su conformidad.
- [ ] **Step 5: Ejecutar** `python -m prevision.pipeline` y `pytest -v`. Expected: sin avisos de enlaces, totales por curso intactos, todo PASS.
- [ ] **Step 6: Commit** `data: enlaces confirmados de centros y umbrales de calidad`.

### Task 6: Notebook, documento y README

**Files:**
- Create: `notebooks/02_exploracion.ipynb`, `docs/fase-2-exploracion.md`, `tests/test_notebook_02.py`
- Modify: `README.md`, `CLAUDE.md` (decisión de series y enlaces)

**Interfaces:**
- Consumes: todas las funciones de las tareas 1 a 4.

- [ ] **Step 1: Escribir `tests/test_notebook_02.py`** igual que `test_notebook.py` pero apuntando a `02_exploracion.ipynb`. Ejecutarlo: Expected: FAIL (no existe el notebook).
- [ ] **Step 2: Crear el notebook** con celdas explicadas que solo llaman a funciones del paquete: hallazgos de la exploración (longitud de series, empiezan tarde, terminan antes, distribución de tamaños), candidatos, enlaces confirmados, series resultantes, calidad, distribución de saltos y la lista de series no elegibles con motivo; última celda: assert de que `enfermeria_series.csv` en memoria es idéntico al del pipeline. Ejecutarlo con kernel `prev-mat` para guardarlo con salidas.
- [ ] **Step 3: Ejecutar** `pytest tests/test_notebook_02.py -v`. Expected: PASS.
- [ ] **Step 4: Escribir `docs/fase-2-exploracion.md`** (qué se hizo, enlaces decididos y por qué, umbrales, cuántas series son elegibles y cuáles no, límites reales: enlaces como juicio, 2025-26 provisional, series cortas). Sin embellecer resultados.
- [ ] **Step 5: Actualizar `README.md`** (fila de fase 2 como hecha, comando del pipeline, estructura con `data/reference/`) y `CLAUDE.md` (enlaces de centros en `data/reference/center_links.csv`, `series_id`).
- [ ] **Step 6: Ejecutar** `pytest -v`. Expected: todo PASS (37 anteriores + nuevos).
- [ ] **Step 7: Commit** `docs: notebook, documento de la fase 2 y README`.

---

## Autorrevisión

- Cobertura del diseño: detección (T1), enlaces y cadenas y solapes e invariante (T2), calidad y elegibilidad (T3), pipeline y aviso sin enlaces (T4), revisión del usuario y umbrales (T5), notebook, doc y README (T6).
- Consistencia de tipos: `n_source_codes` se produce en T2 y lo consume `series_quality` en T3 (`is_linked`).
- Tarea 5 contiene una parada obligatoria: las decisiones sobre enlaces son del usuario.
