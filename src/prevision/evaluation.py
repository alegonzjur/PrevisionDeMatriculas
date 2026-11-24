"""Líneas base y evaluación de origen móvil (fase 3).

Un modelo es una función `historia -> previsión`: recibe la matrícula de una serie hasta el
origen (indexada por `year_start`, sin NaN) y devuelve la previsión del curso siguiente al
último. Así los modelos de la fase 4 se evalúan con el mismo marco.
"""

from collections.abc import Callable

import pandas as pd

from prevision.config import MA_WINDOW


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
