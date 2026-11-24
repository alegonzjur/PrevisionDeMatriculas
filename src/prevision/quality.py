"""Calidad y elegibilidad de las series de centros (fase 2).

Los saltos solo se marcan: no se corrigen, suavizan ni imputan.
"""

import numpy as np
import pandas as pd

from prevision.config import JUMP_RATIO, MIN_SEASONS

QUALITY_COLUMNS = [
    "series_id",
    "university",
    "center_name",
    "first_year",
    "last_year",
    "n_seasons",
    "active_last",
    "size_last",
    "max_jump_ratio",
    "n_jumps",
    "is_linked",
    "eligible",
]


def _jump_ratios(years: np.ndarray, enrolled: np.ndarray) -> np.ndarray:
    """Cocientes `max(r, 1/r)` entre cursos consecutivos con dato en ambos.

    Si falta un curso (hueco o NaN) no se compara a través del hueco, para no
    fabricar un salto falso. Valores no positivos se descartan.
    """
    consecutive = np.diff(years) == 1
    before, after = enrolled[:-1], enrolled[1:]
    valid = consecutive & (before > 0) & (after > 0)
    ratio = after[valid] / before[valid]
    return np.maximum(ratio, 1 / ratio)


def series_quality(
    series: pd.DataFrame,
    min_seasons: int = MIN_SEASONS,
    jump_ratio: float = JUMP_RATIO,
) -> pd.DataFrame:
    """Una fila por `series_id` con longitud, tamaño, saltos y elegibilidad.

    Solo cuentan los cursos con matrícula informada. `active_last` indica que la
    serie llega al último curso del panel; `eligible = active_last and
    n_seasons >= min_seasons`.
    """
    final_year = series["year_start"].max()
    rows = []
    for series_id, group in series.groupby("series_id", sort=True):
        with_data = group.dropna(subset=["enrolled"]).sort_values("year_start")
        years = with_data["year_start"].to_numpy()
        enrolled = with_data["enrolled"].to_numpy(dtype=float)
        ratios = _jump_ratios(years, enrolled)

        n_seasons = len(with_data)
        active_last = n_seasons > 0 and years[-1] == final_year
        latest = group.sort_values("year_start").iloc[-1]
        rows.append(
            {
                "series_id": series_id,
                "university": latest["university"],
                "center_name": latest["center_name"],
                "first_year": years[0] if n_seasons else np.nan,
                "last_year": years[-1] if n_seasons else np.nan,
                "n_seasons": n_seasons,
                "active_last": bool(active_last),
                "size_last": enrolled[-1] if n_seasons else np.nan,
                "max_jump_ratio": ratios.max() if len(ratios) else np.nan,
                "n_jumps": int((ratios > jump_ratio).sum()),
                "is_linked": bool(group["n_source_codes"].iloc[0] > 1),
                "eligible": bool(active_last and n_seasons >= min_seasons),
            }
        )
    return pd.DataFrame(rows, columns=QUALITY_COLUMNS)
