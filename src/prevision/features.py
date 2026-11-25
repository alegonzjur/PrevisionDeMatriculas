"""Variables y ejemplos de entrenamiento de los modelos globales (fase 4).

Un ejemplo es un par (serie, origen `o`): las variables solo usan cursos con dato hasta `o`
y el objetivo es el crecimiento logarítmico del curso siguiente, `ln(y[o+1] / y[o])`.

Garantía contra la fuga de información: antes de calcular nada, la tabla se recorta al
último curso que el cálculo puede ver (`up_to` en los ejemplos, `origin` en las filas de
previsión). Nada posterior a ese curso llega a ninguna variable, tampoco a las medias entre
series (`system_growth`, `region_growth`).
"""

import numpy as np
import pandas as pd

from prevision.config import MIN_FEATURE_HISTORY

FEATURE_SETS: dict[str, list[str]] = {
    "base": ["g1", "g2", "drift_rel", "log_size", "n_seasons", "pct_women", "system_growth"],
}
FEATURE_SETS["with_region"] = FEATURE_SETS["base"] + ["region_growth"]
FEATURE_SETS["without_system"] = [c for c in FEATURE_SETS["base"] if c != "system_growth"]

ALL_FEATURES = FEATURE_SETS["with_region"]
PREDICTION_COLUMNS = ["series_id", "origin_year", "last_value"] + ALL_FEATURES
EXAMPLE_COLUMNS = PREDICTION_COLUMNS + ["target"]

# Una media entre series de la misma región solo se calcula con al menos tantas "otras" series.
MIN_REGION_PEERS = 2


def _origin_table(series: pd.DataFrame, last_year: int) -> pd.DataFrame:
    """Una fila por (serie, curso con dato ≤ `last_year`) con sus variables en ese origen.

    Incluye `next_year` y `next_value` (el curso con dato siguiente, si existe en la tabla
    recortada) para que quien llame decida si hay objetivo.
    """
    data = series[series["year_start"] <= last_year].dropna(subset=["enrolled"])
    bad = data[data["enrolled"] <= 0]
    if not bad.empty:
        raise ValueError(
            "Matrícula cero o negativa (el logaritmo no existe) en las series: "
            f"{sorted(bad['series_id'].unique())}"
        )

    rows = []
    for series_id, group in data.sort_values("year_start").groupby("series_id", sort=True):
        years = group["year_start"].to_numpy()
        values = group["enrolled"].to_numpy(dtype=float)
        pct_women = group["pct_women"].to_numpy(dtype=float)
        logs = np.log(values)
        region = group["region"].iloc[0]
        for p in range(len(group)):
            has_next = p + 1 < len(group)
            rows.append(
                {
                    "series_id": series_id,
                    "region": region,
                    "origin_year": int(years[p]),
                    "last_value": values[p],
                    "g1": logs[p] - logs[p - 1] if p >= 1 else np.nan,
                    "g2": logs[p - 1] - logs[p - 2] if p >= 2 else np.nan,
                    "drift_rel": (
                        ((values[p] - values[0]) / (years[p] - years[0])) / values[p]
                        if p >= 1
                        else np.nan
                    ),
                    "log_size": logs[p],
                    "n_seasons": p + 1,
                    "pct_women": pct_women[p],
                    "next_year": years[p + 1] if has_next else np.nan,
                    "next_value": values[p + 1] if has_next else np.nan,
                }
            )
    table = pd.DataFrame(rows)
    if table.empty:
        return table

    table["system_growth"] = _mean_of_others(table, by=["origin_year"], min_others=1)
    table["region_growth"] = _mean_of_others(
        table, by=["origin_year", "region"], min_others=MIN_REGION_PEERS
    )
    return table


def _mean_of_others(table: pd.DataFrame, by: list[str], min_others: int) -> pd.Series:
    """Media de `g1` de las demás series del grupo (excluye la propia); NaN si hay pocas."""
    g1 = table["g1"]
    has = g1.notna()
    total = g1.fillna(0.0).groupby([table[c] for c in by]).transform("sum")
    count = has.astype(int).groupby([table[c] for c in by]).transform("sum")
    others_sum = total - g1.fillna(0.0)
    others_n = count - has.astype(int)
    return (others_sum / others_n).where(others_n >= min_others)


def build_examples(series: pd.DataFrame, up_to: int) -> pd.DataFrame:
    """Ejemplos de entrenamiento cuyo curso objetivo es `≤ up_to`.

    Una fila por (serie, origen `o`) con `o+1 ≤ up_to`, el curso `o+1` consecutivo y con dato,
    y al menos `MIN_FEATURE_HISTORY` cursos con dato hasta `o`. Columnas: `EXAMPLE_COLUMNS`.
    """
    table = _origin_table(series, last_year=up_to)
    if table.empty:
        return pd.DataFrame(columns=EXAMPLE_COLUMNS)
    keep = (table["next_year"] == table["origin_year"] + 1) & (
        table["n_seasons"] >= MIN_FEATURE_HISTORY
    )
    examples = table[keep].copy()
    examples["target"] = np.log(examples["next_value"] / examples["last_value"])
    return examples[EXAMPLE_COLUMNS].reset_index(drop=True)


def build_prediction_rows(series: pd.DataFrame, origin: int) -> pd.DataFrame:
    """Variables en el origen `origin` de cada serie con dato ese curso y historia suficiente.

    Es la tabla de `build_examples` sin `target`. Solo se ven datos `≤ origin`.
    """
    table = _origin_table(series, last_year=origin)
    if table.empty:
        return pd.DataFrame(columns=PREDICTION_COLUMNS)
    keep = (table["origin_year"] == origin) & (table["n_seasons"] >= MIN_FEATURE_HISTORY)
    return table[keep][PREDICTION_COLUMNS].reset_index(drop=True)
