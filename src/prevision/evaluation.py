"""Líneas base y evaluación de origen móvil (fase 3).

Un modelo es una función `historia -> previsión`: recibe la matrícula de una serie hasta el
origen (indexada por `year_start`, sin NaN) y devuelve la previsión del curso siguiente al
último. Así los modelos de la fase 4 se evalúan con el mismo marco.
"""

from collections.abc import Callable

import pandas as pd

from prevision.config import MA_WINDOW, MIN_TRAIN


def _require_history(history: pd.Series) -> None:
    if len(history) == 0:
        raise ValueError("La historia está vacía: no se puede prever.")


def naive(history: pd.Series) -> float:
    """Ingenuo: el último valor."""
    _require_history(history)
    return float(history.iloc[-1])


def drift(history: pd.Series) -> float:
    """Ingenuo con deriva: último valor más la pendiente media por curso.

    La pendiente es `(último - primero) / (año último - año primero)`, de modo que un
    curso sin dato en medio no distorsiona el cálculo. Con un solo valor devuelve ese valor.
    """
    _require_history(history)
    last = float(history.iloc[-1])
    span = history.index[-1] - history.index[0]
    if span == 0:
        return last
    return last + (last - float(history.iloc[0])) / span


def moving_average(history: pd.Series, window: int = MA_WINDOW) -> float:
    """Media de los últimos `window` cursos (todos los que haya si son menos)."""
    _require_history(history)
    return float(history.iloc[-window:].mean())


BASELINES: dict[str, Callable[[pd.Series], float]] = {
    "naive": naive,
    "drift": drift,
    "moving_average": moving_average,
}


FORECAST_COLUMNS = [
    "series_id",
    "origin_year",
    "target_year",
    "model",
    "y_true",
    "y_pred",
    "is_provisional_target",
]


def rolling_origin_forecasts(
    series: pd.DataFrame,
    models: dict[str, Callable[[pd.Series], float]] = BASELINES,
    min_train: int = MIN_TRAIN,
) -> pd.DataFrame:
    """Previsiones de origen móvil: cada origen `t` prevé el curso `t+1`.

    Un par (serie, origen) existe si `t` es un curso con matrícula informada, la historia
    hasta `t` (solo cursos con dato) tiene al menos `min_train` valores y el curso `t+1`
    tiene dato. La historia se corta por posición antes de llamar al modelo, de modo que
    ningún dato posterior a `t` puede influir en la previsión.

    Devuelve una fila por par y modelo con las columnas de `FORECAST_COLUMNS`.
    """
    rows = []
    for series_id, group in series.groupby("series_id", sort=True):
        data = group.dropna(subset=["enrolled"]).sort_values("year_start")
        years = data["year_start"].to_numpy()
        values = data["enrolled"].to_numpy(dtype=float)
        provisional = data["is_provisional"].to_numpy(dtype=bool)
        for position in range(min_train - 1, len(data) - 1):
            origin, target = years[position], years[position + 1]
            if target != origin + 1:
                continue  # el curso siguiente no tiene dato
            history = pd.Series(values[: position + 1], index=years[: position + 1])
            for name, model in models.items():
                rows.append(
                    {
                        "series_id": series_id,
                        "origin_year": int(origin),
                        "target_year": int(target),
                        "model": name,
                        "y_true": values[position + 1],
                        "y_pred": float(model(history)),
                        "is_provisional_target": bool(provisional[position + 1]),
                    }
                )
    return pd.DataFrame(rows, columns=FORECAST_COLUMNS)
