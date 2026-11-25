# PrevisionDeMatriculas

Previsión del nº de estudiantes matriculados en Grado en Enfermería, por centro, para el curso
siguiente (horizonte: 1 curso). Datos del SIIU (Ministerio de Ciencia, Innovación y Universidades),
cursos 2015-16 a 2025-26. Proyecto personal con foco en el modelo y en aprender MLOps por capas.

El detalle de decisiones y de cada fase está en `docs/`.

## Estado

| Fase | Estado | Documento |
|---|---|---|
| 1. Carga y limpieza | hecha | `docs/fase-1-limpieza.md` |
| 2. Exploración y calidad de series | hecha | `docs/fase-2-exploracion.md` |
| 3. Líneas base y evaluación de origen móvil | hecha | `docs/fase-3-lineas-base.md` |
| 4. Modelos globales (Ridge y gradient boosting) | hecha | `docs/fase-4-modelos.md` |
| 5. MLOps por capas | pendiente | |
| 6. Previsión 2026-27 y documentación | pendiente | |

Decisiones de cada fase y su motivo: `docs/decisiones.md`.

## Estructura

```
data/raw/         Excel original del SIIU (no se modifica nunca)
data/reference/   decisiones a mano que sí se versionan (enlaces de centros)
data/processed/   salida del pipeline (no se versiona)
src/prevision/    código del proyecto (carga, limpieza, validación, enlaces, calidad, variables, evaluación, pipeline)
notebooks/        un notebook por fase con los pasos explicados
tests/            pruebas con pytest
docs/             un documento por fase y el registro de decisiones
```

## Cómo ejecutar

Entorno conda `prev-mat` (Python 3.11):

```bash
conda activate prev-mat
pip install -e ".[notebooks]"
python -m prevision.pipeline    # genera en data/processed/: panel, series, calidad y evaluación de líneas base y modelos
pytest
```

Para actualizar con datos nuevos, sustituye `data/raw/Matriculados.xlsx` y vuelve a lanzar
`python -m prevision.pipeline`. Los notebooks `notebooks/01_limpieza.ipynb`, `notebooks/02_exploracion.ipynb`, `notebooks/03_lineas_base.ipynb` y `notebooks/04_modelos.ipynb` dejan constancia de los pasos.
Los enlaces de centros que cambian de código se confirman a mano en `data/reference/center_links.csv`.
