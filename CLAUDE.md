
# Previsión de matrícula en Enfermería (SIIU)

## Objetivo
Proyecto de MLOps de tamaño reducido: prever el nº de estudiantes matriculados
en Grado en Enfermería, por centro, para el curso siguiente (horizonte: 1 curso).

## Decisiones tomadas
- Unidad de análisis: panel por centro (universidad + código de centro), no solo total nacional.
- Variable objetivo: matriculados totales (no nuevo ingreso; posible ampliación futura).
- Evaluación: validación de origen móvil, siempre comparada con un modelo ingenuo.
- Datos: SIIU (Ministerio de Ciencia, Innovación y Universidades), cursos 2015-16 a 2025-26.
- Enfoque: modelo primero, MLOps por capas (MLflow, DVC/pipeline, CI, Streamlit), cada
  herramienta cuando resuelva un problema real. Prioridad: calidad del modelo y su evaluación.
- `data/raw/Egresados.xlsx` queda fuera por ahora.
- Decisiones de cada fase y su motivo: docs/decisiones.md (se actualiza al cerrar cada fase).
- Los diseños y planes de trabajo (docs/superpowers/) son material LOCAL: no se versionan ni se suben a
  GitHub (están en .gitignore). Lo que debe quedar para el proyecto va a docs/decisiones.md.

## Datos
- Fichero original: data/raw/Matriculados.xlsx. NO modificar nunca.
- Hojas relevantes: "Matriculados Grado" y "Matriculados Global por centro".
- Cabecera real en la fila 4; después van pares de columnas Total / % Mujeres por curso.
- 2025-26 es un dato PROVISIONAL (avance) y puede revisarse.
- NaN = titulación sin dato ese curso (no hay ceros).

## Reglas de limpieza (documentar cada una)
- Quedarse solo con "Graduado o Graduada en Enfermería". El título aparece también como
  "Graduado o Graduada en Enfermería por la Universidad de X": la regla admite ese sufijo.
- Excluir Diplomado en Enfermería, programas conjuntos (PCEO / dobles grados), másteres y doctorados.
- Algunas series se parten por cambios de código de titulación (p. ej. Granada, Almería):
  unificar por universidad + código de centro (el nombre puede cambiar con el mismo código)
  y SUMAR los códigos de titulación del centro por curso (suma con NaN si todos son NaN).
- Cambio de adscripción conocido: Centro de Enfermería San Juan de Dios (Univ. Sevilla)
  pasa a EUEF San Juan de Dios (Univ. Pontificia Comillas). Decisión: se dejan como
  DOS series separadas (no se suman). Documentado en docs/fase-1-limpieza.md.
- El resultado de la limpieza está en data/processed/ (no se versiona; se regenera con
  `python -m prevision.pipeline`). Cada regla queda en el registro de limpieza.

## Series y enlaces de centros (fase 2)
- El panel de la fase 1 es rectangular: un curso sin dato es una fila con `enrolled` NaN. Para
  "primer/último curso" de un centro, contar solo los cursos con matrícula informada.
- Los cambios de código de centro (misma universidad) se enlazan a mano en
  `data/reference/center_links.csv` (se versiona; `decision` = sí/no/dudoso, solo `sí` se aplica; cada
  fila lleva una nota). La decisión de enlazar es siempre de la persona, nunca automática.
- `series_id = "{universidad}|{código de centro más reciente de la cadena}"`. Una serie no puede
  bifurcarse ni formar ciclos (error). La matrícula total por curso no cambia al enlazar (se comprueba).
- Salida en `data/processed/`: `enfermeria_series.csv`, `series_quality.csv`, `link_candidates.csv`.
- Elegible para prever = llega al último curso y tiene al menos `MIN_SEASONS` (4) cursos con dato.
  `JUMP_RATIO` (1,5) solo marca saltos: no se corrigen. Ambos en `config.py`. Límites y casos sin
  enlazar (p. ej. Nebrija 28051891 → 28055225 y Murcia 30013116 → 30011821, enlazados a mano; València La Fe, `dudoso`) en docs/fase-2-exploracion.md.

## Evaluación y líneas base (fase 3)
- Un modelo es una función `historia -> previsión` (historia: matrícula por `year_start`, sin NaN, hasta el
  origen). Los de la fase 4 se evalúan con `rolling_origin_forecasts` y `compute_metrics`, sin tocar el marco.
- Origen móvil: el origen `t` ve solo cursos con dato hasta `t` y prevé `t+1`. `MIN_TRAIN` = 4 cursos con dato,
  `MA_WINDOW` = 3. Solo series elegibles. Hay un test de no-fuga: no hay que debilitarlo.
- Métricas: MAE, WAPE, MAPE y sesgo, por curso objetivo y total, con y sin 2025-26 (provisional). Siempre
  junto al ingenuo (`*_vs_naive`).
- Listón actual (docs/fase-3-lineas-base.md): WAPE ingenuo 4,7 %, deriva 4,3 %, media móvil 7,7 %. La deriva
  solo gana en centros grandes. Salidas: `baseline_forecasts.csv` y `baseline_metrics.csv`.

## Modelos globales (fase 4)
- `rolling_origin_global(series)` (evaluation.py): en cada origen `t` ajusta cada modelo con los ejemplos de
  `build_examples(series, up_to=t)` (objetivo `<= t`) y prevé `t+1` sobre los MISMOS pares que las líneas base.
  Predice `ln(y[t+1]/y[t])`; previsión = último valor · exp(predicción). `GLOBAL_MODELS`: `ridge` y `gbm`
  (variables `base`, versión principal) y las variantes `*_region` y `*_no_system` (solo sensibilidad).
- Variables (features.py, `FEATURE_SETS`): `g1`, `g2`, `drift_rel`, `log_size`, `n_seasons`, `pct_women`,
  `system_growth` (+ `region_growth`). La tabla se recorta al último curso visible antes de calcular nada. Sin
  identificador de universidad ni de centro. La región es la CCAA del Excel, no se deriva del código de centro.
- Hiperparámetros fijos en `config.py` (`RIDGE_ALPHA`, `GBM_PARAMS`, `MIN_TRAIN_EXAMPLES`...): NUNCA se ajustan con
  los pares de evaluación; cualquier cambio es sensibilidad y se rotula. Error, no relleno, si faltan ejemplos.
- Criterio de éxito (declarado antes de ver resultados): WAPE total menor que la deriva Y no peor que el ingenuo
  en los tramos mediano y pequeño. Resultado (docs/fase-4-modelos.md): ninguno lo supera. `gbm` 4,04 % y `ridge`
  4,22 % frente a deriva 4,30 % e ingenuo 4,71 %, pero ambos peores que el ingenuo en centros pequeños.
- Salidas: `model_forecasts.csv` (solo modelos globales) y `model_metrics.csv` (líneas base y modelos).

## Entorno
- Windows, conda (entorno: prev-mat), Python 3.11. Instalación: `pip install -e ".[notebooks]"`.
- Código en src/prevision/ (paquete), tests con pytest, notebooks en notebooks/.
- Control de versiones con git: UNA RAMA POR FASE (p. ej. fase-1-limpieza), integrada por Pull Request.
- Cada fase deja: un documento en docs/ (docs/fase-N-*.md), un notebook que deja constancia de los
  pasos y el mismo código disponible como pipeline. El notebook llama a las funciones del paquete,
  sin lógica propia, para que notebook y pipeline no puedan divergir.

## Cómo quiero trabajar
- Explica el razonamiento ANTES de implementar y espera mi conformidad en cambios grandes.
- Diagnostica antes de arreglar: no apliques parches sin entender la causa.
- Documenta los límites y errores reales; no embellezcas los resultados.
- Documentación y comentarios en español; nombres de variables y funciones en inglés.
- Entrega ficheros completos y listos para usar, de uno en uno.