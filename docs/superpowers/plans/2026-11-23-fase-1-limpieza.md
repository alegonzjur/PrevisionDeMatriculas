# Fase 1: carga y limpieza. Plan de implementación

> **Para quien ejecute:** usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans, tarea a tarea. Los pasos usan casillas `- [ ]`.

**Objetivo:** convertir `data/raw/Matriculados.xlsx` en un panel limpio por centro (universidad + código de centro) de Grado en Enfermería, con cada regla de limpieza documentada, testeada y registrada con el nº de filas afectadas. Dos entregables que usan el mismo código: un **notebook** que deja constancia de cada paso y un **`pipeline.py` ETL** para repetir el proceso cuando se actualicen los datos.

**Arquitectura:** paquete Python `prevision` en `src/`, instalable en modo editable. Flujo: leer hoja (ancho) → filtrar titulación (ancho) → pasar a formato largo → unificar series por centro → validar contra la hoja "Matriculados Grado". Un `CleaningLog` recoge cada paso. `pipeline.py` se organiza en `extract` / `transform` / `load`. El notebook `notebooks/01_limpieza.ipynb` llama, paso a paso y con explicación, a las mismas funciones del paquete (una sola fuente de código: notebook y pipeline no pueden divergir).

**Tecnología:** Python 3.11, pandas, openpyxl, pytest. Entorno conda **`prev-mat`**, con pandas 3.1.1, openpyxl 3.1.5 y pytest 9.2.0. Para el notebook hay que añadir `ipykernel`, `nbformat`, `nbclient` y `nbconvert` (hoy no están en `prev-mat`) y registrar el kernel.

**Diseño de referencia:** `docs/superpowers/specs/2026-11-23-prevision-matriculas-design.md` (sección 5, fase 1).

**Rama:** `fase-1-limpieza`. **Documento de la fase:** `docs/fase-1-limpieza.md` (tarea 6).

## Hallazgos del diagnóstico previo (datos reales)

Leídos solo en lectura, sin modificar el Excel.

- Cabecera de columnas en la fila 4 (índice 3). Los cursos están en la fila 3 (índice 2), solo sobre la columna *Total* de cada par (Total, % Mujeres). Orden de más reciente a más antiguo: 2025-2026 … 2015-2016 (11 cursos). Los códigos son texto con ceros a la izquierda (p. ej. `04008558`).
- La hoja "Matriculados Global por centro" mezcla `Nivel` Grado (7914 filas), Máster (7522) y Doctorado (2338).
- **La titulación no siempre es el texto literal de `CLAUDE.md`.** Hay 8 filas "Graduado o Graduada en Enfermería" y muchas más "Graduado o Graduada en Enfermería por la Universidad de X". Con el literal exacto se perderían casi todos los centros. Con el patrón `^Graduado o Graduada en Enfermería( por .*)?$` salen **158 filas, 145 combinaciones universidad+centro, 70 universidades**, todas de nivel Grado.
- 13 filas comparten universidad + nombre de centro con otro código de titulación (cambios de plan). Ejemplos:
  - Almería: `2501129` (hasta 2016-17) y `2504090` (desde 2025-26), sin solapamiento.
  - Granada: `1500083` (solo 2025-26, 199) y `2501351` (todos los cursos, 613 en 2025-26), con solapamiento.
- El nombre del centro puede cambiar con el mismo código: Melilla (`52000452`) aparece como "Facultad de Ciencias de la Salud de Melilla" y como "Facultad de Enfermería de Melilla".
- San Juan de Dios: Sevilla `41015500` ("Centro de Enfermería San Juan de Dios") tiene 67/87 en 2025-26/2024-25 y 233 en 2016-17. Pontificia Comillas `28042772` (EUEF San Juan de Dios) tiene 1195/949 y 473. **Ambos tienen datos en los mismos cursos.** Comillas tiene además otro centro, `07009045` (Alberta Giménez), que no forma parte del caso.

### Decisiones confirmadas por el autor

1. **Patrón de titulación** ampliado a "…por la Universidad de X".
2. **Clave de unificación = (universidad, código de centro)**, con el nombre más reciente como etiqueta (el nombre cambia, p. ej. Melilla; el código no).
3. **Los códigos de titulación dentro de un centro se suman por curso** (`sum(min_count=1)`: todo NaN sigue siendo NaN, nunca 0). Vale para cambio de plan sin solape (Almería) y con solape (Granada 2025-26).
4. **San Juan de Dios (Sevilla) y Pontificia Comillas se dejan como series separadas.** No hay reasignación de centros en esta fase. Se documenta como caso especial en `docs/fase-1-limpieza.md` (no se unen porque hay datos de ambos en los mismos cursos).
5. **Entorno: `prev-mat`** (`CLAUDE.md` dice `matricula-enf`; hay que corregirlo allí).
6. **Notebook + `pipeline.py`:** el notebook deja constancia de los pasos; `pipeline.py` los repite como ETL cuando haya datos nuevos.

### Decisiones propias del asistente (revisar)

- Notebook y pipeline comparten las funciones del paquete en vez de duplicar código: así, si se corrige una regla, cambia en los dos sitios. El coste es que el código de las reglas se lee en `src/`, no dentro del notebook.
- `data/processed/` no se versiona por ahora (se regenera con un comando). DVC llega en la fase 5.
- El notebook se guarda **con las salidas ejecutadas**, para que se vea en GitHub sin ejecutarlo, y un test lo ejecuta de principio a fin.

## Restricciones globales

- Windows, conda (entorno `prev-mat`), Python 3.11, tests con pytest, control de versiones con git.
- El notebook no contiene lógica propia: solo llama a funciones de `prevision` y muestra resultados. El pipeline y el notebook deben producir el mismo panel.
- `data/raw/Matriculados.xlsx` **no se modifica nunca** (hay un test de hash).
- Hojas relevantes: "Matriculados Grado" (validación) y "Matriculados Global por centro" (panel). Cabecera real en la fila 4; después, pares Total / % Mujeres por curso.
- 2025-26 es dato **provisional** (`is_provisional = True`). NaN = titulación sin dato ese curso: no hay ceros ni se rellenan.
- Solo "Graduado o Graduada en Enfermería". Excluir Diplomado, programas conjuntos (PCEO / dobles grados), másteres y doctorados.
- Documentación y comentarios en español; nombres de variables, funciones y columnas en inglés.
- Cada fase, una rama. Los mensajes de commit terminan con la línea `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Entregar ficheros completos, de uno en uno, explicando el razonamiento antes en los cambios grandes.

## Revisión: casos que el diseño implica y la mayoría de pruebas no cubre

1. Título con sufijo "por la Universidad de X" debe conservarse (tarea 2).
2. Un curso con NaN en todos los códigos de un centro debe seguir siendo NaN, no 0 (tarea 3).
3. Cambio de código sin solape (Almería) y con solape (Granada 2025-26) dan la suma correcta (tarea 3).
4. Mismo código de centro con nombre distinto (Melilla): una sola serie con el nombre más reciente (tarea 3).
5. Cabecera desconocida o filas finales vacías en el Excel: error claro o se ignoran, nunca datos corruptos (tarea 1).
6. San Juan de Dios (Sevilla) y Comillas deben salir como dos series distintas, sin sumarse (tarea 5).
7. El notebook ejecutado de principio a fin debe dar el mismo panel que el pipeline (tarea 6).

## Estructura de ficheros

- `pyproject.toml`: metadatos y dependencias; extra `notebooks`; instalación editable.
- `.gitignore`: `data/processed/`, cachés, `.ipynb_checkpoints` y `*.egg-info`.
- `src/prevision/__init__.py`
- `src/prevision/config.py`: constantes (rutas, hojas, patrón, mapa de columnas).
- `src/prevision/loading.py`: `read_raw_sheet`, `wide_to_long`.
- `src/prevision/cleaning.py`: `CleaningLog`, `filter_nursing_degrees`, `unify_center_series`.
- `src/prevision/validation.py`: `compare_university_totals`.
- `src/prevision/pipeline.py`: ETL (`extract`, `transform`, `load`, `run_pipeline`) y CLI.
- `notebooks/01_limpieza.ipynb`: recorrido explicado de la fase.
- `tests/conftest.py`: constructor del Excel de prueba.
- `tests/test_loading.py`, `test_cleaning.py`, `test_validation.py`, `test_pipeline.py`, `test_notebook.py`.
- `docs/fase-1-limpieza.md`: documento de la fase.

---

### Task 1: carga de la hoja y formato largo

**Archivos:**
- Crear: `pyproject.toml`, `.gitignore`, `src/prevision/__init__.py`, `src/prevision/config.py`, `src/prevision/loading.py`, `tests/conftest.py`, `tests/test_loading.py`

**Interfaces:**
- Produce en `config.py`: `RAW_FILE: Path`, `SHEET_CENTERS: str`, `SHEET_DEGREES: str`, `SEASON_ROW: int = 2`, `HEADER_ROW: int = 3`, `LEVEL_PREFIX: str = "Grado"`, `NURSING_DEGREE_PATTERN: str`, `PROVISIONAL_YEAR: int = 2025`, `COLUMN_MAP: dict[str, str]` (cabecera Excel → nombre inglés: `level`, `region`, `university`, `center_code`, `center_name`, `degree_code`, `degree_name`, `branch`; "Código de titulación" y "Código Titulación" → `degree_code`), `PROCESSED_DIR: Path = Path("data/processed")`.
- Produce `read_raw_sheet(path: Path, sheet: str) -> pd.DataFrame` (ancho): columnas fijas en inglés (códigos como `str` sin espacios) más `enrolled_{year_start}` y `pct_women_{year_start}` (float, NaN conservado). Ignora filas totalmente vacías. Lanza `ValueError` si una cabecera fija no está en `COLUMN_MAP`.
- Produce `wide_to_long(wide: pd.DataFrame) -> pd.DataFrame`: columnas fijas + `year_start: int`, `season: str` (p. ej. `"2025-2026"`), `enrolled: float`, `pct_women: float`, `is_provisional: bool`.
- Produce `tests/conftest.py::build_workbook(path: Path, centers_rows: list[dict], degrees_rows: list[dict], years: tuple[int, ...] = (2025, 2024, 2023)) -> Path`: escribe con openpyxl un Excel con las dos hojas, tres filas de título, cursos en la fila 3 y cabecera en la fila 4, imitando el real. Cada dict lleva las claves en inglés de `COLUMN_MAP` más `values: dict[int, tuple[float | None, float | None]]` (año → (total, % mujeres)).

- [ ] **Paso 1: `pyproject.toml`, `.gitignore`, paquete vacío** y `pip install -e .` en el entorno `prev-mat`. En `pyproject.toml`, dependencias `pandas`, `openpyxl` y extra `notebooks` (`ipykernel`, `nbformat`, `nbclient`, `nbconvert`). Comprobar: `python -c "import prevision"` sin error.
- [ ] **Paso 2: escribir `build_workbook` y los tests (deben fallar)** en `tests/test_loading.py`:
  - `test_read_raw_sheet_names_columns_and_keeps_codes_as_text`: `center_code == "04008558"` (cero inicial conservado) y existen `enrolled_2025`, `pct_women_2024`.
  - `test_read_raw_sheet_keeps_nan_not_zero`: una celda vacía queda `NaN`.
  - `test_read_raw_sheet_ignores_trailing_empty_rows`: el nº de filas es el de las filas con datos.
  - `test_read_raw_sheet_rejects_unknown_header` (`pytest.raises(ValueError)`).
  - `test_wide_to_long_season_and_provisional`: `season` de `year_start=2024` es `"2024-2025"`, y solo `2025` tiene `is_provisional == True`.
  - `test_wide_to_long_row_count`: filas = filas anchas × nº de cursos.
- [ ] **Paso 3: ejecutar** `pytest tests/test_loading.py -v`. Esperado: FAIL (módulo sin implementar).
- [ ] **Paso 4: implementar** `config.py` y `loading.py` con las firmas de Interfaces. La fila de cursos se propaga a la derecha sobre el par Total / % Mujeres; leer con `header=None, dtype=object`.
- [ ] **Paso 5: ejecutar** `pytest tests/test_loading.py -v`. Esperado: PASS.
- [ ] **Paso 6: test sobre el fichero real** (se omite si no existe): `test_real_centers_sheet_has_11_seasons`: `read_raw_sheet(RAW_FILE, SHEET_CENTERS)` tiene 11 columnas `enrolled_*` (2015…2025). Ejecutar. Esperado: PASS.
- [ ] **Paso 7: commit** `feat: carga de hojas SIIU y paso a formato largo`.

### Task 2: registro de limpieza y filtro de titulación

**Archivos:**
- Crear: `src/prevision/cleaning.py`, `tests/test_cleaning.py`

**Interfaces:**
- Consume: `config.LEVEL_PREFIX`, `config.NURSING_DEGREE_PATTERN`.
- Produce `CleaningLog` con `add(rule_id: str, description: str, before: int, after: int) -> None`, atributo `entries: list[dict]` (claves `rule_id`, `description`, `before`, `after`) y `to_markdown() -> str` (tabla con columnas regla, descripción, antes, después, diferencia).
- Produce `filter_nursing_degrees(wide: pd.DataFrame, log: CleaningLog) -> pd.DataFrame`: conserva filas con `level` que empieza por `"Grado"` y `degree_name` que cumple el patrón. Registra una entrada por regla (nivel, titulación), contando filas del Excel.

- [ ] **Paso 1: tests (deben fallar)** con un DataFrame ancho mínimo:
  - `test_keeps_literal_title` y `test_keeps_title_with_university_suffix` (`"Graduado o Graduada en Enfermería por la Universidad de Granada"` se conserva; revisión nº 1).
  - `test_drops_diplomado`, `test_drops_pceo_double_degrees` (`"PCEO Grado en Fisioterapia / Grado en Enfermería"`), `test_drops_master_and_doctorate_titles`.
  - `test_drops_non_grado_level`: una fila con `level == "Máster"` y título válido se elimina.
  - `test_log_records_rows_before_and_after`: las entradas suman la diferencia total de filas.
  - `test_log_to_markdown_contains_rule_ids`.
- [ ] **Paso 2: ejecutar** `pytest tests/test_cleaning.py -v`. Esperado: FAIL.
- [ ] **Paso 3: implementar** `CleaningLog` y `filter_nursing_degrees` (comparar con `str.match` sobre el patrón de config).
- [ ] **Paso 4: ejecutar.** Esperado: PASS.
- [ ] **Paso 5: test sobre datos reales:** `test_real_filter_gives_158_rows`: tras filtrar la hoja de centros real quedan 158 filas. Si el número no coincide, **parar y diagnosticar** antes de seguir.
- [ ] **Paso 6: commit** `feat: filtro de titulación de Enfermería y registro de limpieza`.

### Task 3: unificación de series por centro

**Archivos:**
- Modificar: `src/prevision/cleaning.py`, `tests/test_cleaning.py`

**Interfaces:**
- Consume: salida de `wide_to_long`.
- Produce `unify_center_series(long: pd.DataFrame, log: CleaningLog) -> pd.DataFrame`: una fila por (`university`, `center_code`, `year_start`) con columnas `university, center_code, center_name, year_start, season, enrolled, pct_women, is_provisional`. `enrolled` = suma con `min_count=1`. `pct_women` = mujeres / matriculados, ponderando por `enrolled`. `center_name` = nombre del curso más reciente con dato. Registra nº de series antes (por código de titulación) y después, y nº de celdas centro-curso en que más de un código aporta dato (solapes).

- [ ] **Paso 1: tests (deben fallar):**
  - `test_unify_sums_codes_without_overlap` (Almería: código A hasta 2016, código B desde 2025: cada curso conserva su valor).
  - `test_unify_sums_codes_with_overlap` (Granada 2025: 199 + 613 = 812).
  - `test_unify_all_nan_stays_nan` (revisión nº 2).
  - `test_unify_same_code_different_name_gives_one_series_with_latest_name` (Melilla; revisión nº 4).
  - `test_unify_weighted_pct_women`: 100 con 0.5 y 300 con 0.9 → 0.8.
  - `test_unify_output_is_unique_per_center_and_year` y `test_unify_has_no_zero_filled_missing`.
  - `test_unify_keeps_sevilla_and_comillas_san_juan_de_dios_separate`: las claves `("Sevilla", "41015500")` y `("Pontificia Comillas", "28042772")` siguen siendo dos series con sus valores originales (revisión nº 6).
- [ ] **Paso 2: ejecutar.** Esperado: FAIL.
- [ ] **Paso 3: implementar** `unify_center_series`. `pct_women` NaN cuando `enrolled` es NaN o 0.
- [ ] **Paso 4: ejecutar.** Esperado: PASS.
- [ ] **Paso 5: commit** `feat: unificación de series por centro`.

### Task 4: validación frente a la hoja de Grado

**Archivos:**
- Crear: `src/prevision/validation.py`, `tests/test_validation.py`

**Interfaces:**
- Consume: dos DataFrames largos ya filtrados, de la hoja de centros y de la hoja de Grado.
- Produce `compare_university_totals(centers_long: pd.DataFrame, degrees_long: pd.DataFrame) -> pd.DataFrame`: filas con `university, year_start, enrolled_centers, enrolled_degrees` donde ambos totales por universidad y curso (suma con `min_count=1`) difieren. Vacío si coinciden.

- [ ] **Paso 1: tests (deben fallar):** `test_no_differences_when_totals_match`, `test_reports_university_and_year_when_totals_differ`, `test_all_nan_on_both_sides_is_not_a_difference`.
- [ ] **Paso 2: ejecutar.** Esperado: FAIL.
- [ ] **Paso 3: implementar.**
- [ ] **Paso 4: ejecutar.** Esperado: PASS.
- [ ] **Paso 5: comprobación con datos reales:** `test_real_university_totals_match_grado_sheet` debe dar un DataFrame vacío. Si no lo da, **parar, diagnosticar y consultar al autor** antes de seguir (puede revelar filas perdidas o dobles contadas). No relajar el test sin entender la causa.
- [ ] **Paso 6: commit** `feat: validación de totales por universidad contra la hoja de Grado`.

### Task 5: pipeline ETL y salida a `data/processed`

**Archivos:**
- Crear: `src/prevision/pipeline.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consume: todo lo anterior.
- Produce `extract(raw_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]`: hojas de centros y de Grado en formato ancho (salida de `read_raw_sheet`).
- Produce `transform(centers_wide: pd.DataFrame, degrees_wide: pd.DataFrame) -> tuple[pd.DataFrame, CleaningLog]`: filtra ambas hojas, valida totales por universidad (registra en el log el nº de diferencias), pasa a largo y `unify_center_series`. Devuelve el panel y el log.
- Produce `load(panel: pd.DataFrame, log: CleaningLog, out_dir: Path = PROCESSED_DIR) -> tuple[Path, Path]`: escribe `enfermeria_panel.csv` (UTF-8) y `cleaning_log.md`, y devuelve sus rutas.
- Produce `run_pipeline(raw_path: Path = RAW_FILE, out_dir: Path = PROCESSED_DIR) -> pd.DataFrame` (encadena las tres) y `main() -> None` (`python -m prevision.pipeline`).

- [ ] **Paso 1: tests (deben fallar)** con `build_workbook`:
  - `test_run_pipeline_end_to_end_on_fixture`: columnas y nº de filas esperados; los dos ficheros se crean en `tmp_path`.
  - `test_run_pipeline_does_not_modify_raw_file`: el hash SHA-256 del Excel es igual antes y después.
  - `test_transform_log_has_one_entry_per_rule`.
  - `test_real_panel_invariants`: sobre el fichero real, el nº de centros del panel es el de pares (universidad, código de centro) distintos tras el filtro (se calcula en el test, no se fija a mano); 11 cursos por centro; `year_start` entre 2015 y 2025; solo 2025 es provisional; sin duplicados (centro, curso); ningún `enrolled` negativo; Sevilla `41015500` y Comillas `28042772` son dos centros distintos.
- [ ] **Paso 2: ejecutar.** Esperado: FAIL.
- [ ] **Paso 3: implementar** `extract`, `transform`, `load`, `run_pipeline` y `main`.
- [ ] **Paso 4: ejecutar toda la batería:** `pytest -v`. Esperado: todo PASS.
- [ ] **Paso 5: ejecutar** `python -m prevision.pipeline` y revisar el log y el CSV (`git status` no debe listar nada de `data/processed/`).
- [ ] **Paso 6: commit** `feat: pipeline ETL y salida del panel`.

### Task 6: notebook de la fase

**Archivos:**
- Crear: `notebooks/01_limpieza.ipynb`, `tests/test_notebook.py`

**Interfaces:**
- Consume: `read_raw_sheet`, `filter_nursing_degrees`, `wide_to_long`, `unify_center_series`, `compare_university_totals`, `CleaningLog`, `config` y `load` (para comparar con la salida del pipeline).
- Produce un notebook en español que recorre la fase en este orden, con una celda de texto antes de cada celda de código que explica el porqué: 1) estructura del Excel (cabecera en la fila 4, cursos en la fila 3); 2) lectura y vista del formato ancho; 3) filtro de titulación con el recuento antes y después de cada regla, e ilustración de por qué falla el texto literal; 4) paso a formato largo; 5) unificación de series, con Almería y Granada como ejemplos de cambio de código; 6) caso San Juan de Dios (Sevilla y Comillas, series separadas, mostradas juntas); 7) validación contra la hoja de Grado; 8) resultado final y el log; 9) comprobación de que el panel es idéntico al de `run_pipeline`. Sin lógica propia: todo son llamadas al paquete.
- Produce `test_notebook.py::test_notebook_runs_end_to_end`: ejecuta el notebook con `nbclient` desde la raíz del repositorio y comprueba que no hay celdas con error.

- [ ] **Paso 1: preparar el entorno:** `pip install -e ".[notebooks]"` y `python -m ipykernel install --user --name prev-mat`. Comprobar con `jupyter kernelspec list` que aparece `prev-mat`.
- [ ] **Paso 2: test (debe fallar)** `test_notebook_runs_end_to_end` (se omite con `pytest.importorskip("nbclient")` y si falta el Excel real). Ejecutar: FAIL (no hay notebook).
- [ ] **Paso 3: crear el notebook** con `nbformat`, kernel `prev-mat`, sin salidas.
- [ ] **Paso 4: ejecutarlo** de principio a fin y guardarlo con salidas. Revisar que ninguna salida sea sospechosa (recuentos coherentes con `cleaning_log.md`).
- [ ] **Paso 5: ejecutar** `pytest -v`. Esperado: todo PASS.
- [ ] **Paso 6: commit** `docs: notebook de limpieza de la fase 1`.

### Task 7: documento de la fase y cierre de la rama

**Archivos:**
- Crear: `docs/fase-1-limpieza.md`
- Modificar: `README.md`, `CLAUDE.md` (solo el nombre del entorno: `prev-mat`, y la nota sobre San Juan de Dios: series separadas), con permiso del autor

- [ ] **Paso 1: redactar `docs/fase-1-limpieza.md`** en español, con: objetivo; estructura del Excel; cada regla con su motivo y el nº de filas afectadas copiado de `cleaning_log.md`; las decisiones confirmadas por el autor (patrón, clave de unificación, suma de códigos, San Juan de Dios separado, notebook + pipeline); límites y errores reales (2025-26 provisional, series cortas, caso San Juan de Dios sin unificar, lo que no se pudo verificar); cómo reproducirlo y cómo actualizar los datos (`pip install -e ".[notebooks]"`, `python -m prevision.pipeline`, abrir el notebook, `pytest`).
- [ ] **Paso 2: actualizar `README.md`** con descripción breve, estructura y cómo ejecutar la fase 1.
- [ ] **Paso 3: proponer al autor** el cambio de `CLAUDE.md` y aplicarlo solo si lo aprueba.
- [ ] **Paso 4: ejecutar** `pytest -v`. Esperado: todo PASS.
- [ ] **Paso 5: commit** `docs: documento de la fase 1 y README`.
- [ ] **Paso 6: no fusionar sin permiso.** Mostrar `git log --oneline main..fase-1-limpieza` y explicar al autor las opciones (merge con `--no-ff`, pull request o dejar la rama), para que elija.
