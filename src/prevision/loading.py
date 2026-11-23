"""Lectura de las hojas del Excel SIIU y paso de formato ancho a formato largo."""

from pathlib import Path

import pandas as pd

from prevision.config import (
    COLUMN_MAP,
    HEADER_ROW,
    PROVISIONAL_YEAR,
    SEASON_ROW,
)

CODE_COLUMNS = ("center_code", "degree_code")


def _as_code(value):
    """Código como texto sin espacios; conserva ceros a la izquierda."""
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_raw_sheet(path: Path, sheet: str) -> pd.DataFrame:
    """Lee una hoja del SIIU y la devuelve en formato ANCHO con nombres en inglés.

    Columnas fijas (university, center_code, degree_name...) más, por cada curso,
    `enrolled_{año}` y `pct_women_{año}` (float; NaN = sin dato, nunca 0).
    El fichero solo se lee, no se modifica.
    """
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    season_labels = raw.iloc[SEASON_ROW]
    headers = raw.iloc[HEADER_ROW]

    # El curso aparece solo sobre la columna "Total" de cada par (Total, % Mujeres).
    season_cols = [i for i, label in enumerate(season_labels) if pd.notna(label)]
    if not season_cols:
        raise ValueError(f"No se encontraron cursos en la fila {SEASON_ROW + 1} de '{sheet}'")
    n_fixed = season_cols[0]

    fixed_names = []
    for header in headers.iloc[:n_fixed]:
        if header not in COLUMN_MAP:
            raise ValueError(f"Cabecera desconocida en '{sheet}': {header!r}")
        fixed_names.append(COLUMN_MAP[header])

    body = raw.iloc[HEADER_ROW + 1 :].dropna(how="all")  # ignora filas finales vacías
    data = body.iloc[:, :n_fixed].copy()
    data.columns = fixed_names
    for column in CODE_COLUMNS:
        if column in data.columns:
            data[column] = data[column].map(_as_code)

    values = {}
    for i in season_cols:
        year = int(str(season_labels.iloc[i])[:4])
        values[f"enrolled_{year}"] = pd.to_numeric(body.iloc[:, i])
        values[f"pct_women_{year}"] = pd.to_numeric(body.iloc[:, i + 1])
    wide = pd.concat([data, pd.DataFrame(values)], axis=1)
    return wide.reset_index(drop=True)


def wide_to_long(wide: pd.DataFrame) -> pd.DataFrame:
    """Pasa de una columna por curso a una fila por (titulación, curso).

    Añade year_start (int), season ("2025-2026"), enrolled, pct_women e
    is_provisional (True solo para el curso provisional).
    """
    value_columns = [c for c in wide.columns if c.startswith(("enrolled_", "pct_women_"))]
    id_columns = [c for c in wide.columns if c not in value_columns]
    years = sorted({int(c.rsplit("_", 1)[1]) for c in value_columns}, reverse=True)

    parts = []
    for year in years:
        part = wide[id_columns].copy()
        part["year_start"] = year
        part["season"] = f"{year}-{year + 1}"
        part["enrolled"] = wide[f"enrolled_{year}"]
        part["pct_women"] = wide[f"pct_women_{year}"]
        part["is_provisional"] = year == PROVISIONAL_YEAR
        parts.append(part)
    return pd.concat(parts, ignore_index=True)
