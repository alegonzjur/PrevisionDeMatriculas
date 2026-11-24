"""Tests de las líneas base y de la evaluación de origen móvil (fase 3)."""

import pandas as pd
import pytest

from prevision.evaluation import BASELINES, drift, moving_average, naive


def _h(values, first_year=2020):
    """Historia de matrícula indexada por cursos consecutivos."""
    return pd.Series(
        values, index=range(first_year, first_year + len(values)), dtype=float
    )


def test_naive_returns_last_value():
    assert naive(_h([100, 110, 120])) == 120


def test_drift_extends_average_yearly_change():
    # (120 - 100) / 3 cursos de diferencia = 6,67 por curso
    assert drift(_h([100, 110, 130, 120])) == pytest.approx(120 + 20 / 3)


def test_drift_uses_year_gaps():
    history = pd.Series([100.0, 120.0], index=[2020, 2022])
    assert drift(history) == pytest.approx(130.0)  # pendiente por año, no por posición


def test_drift_single_value_returns_it():
    assert drift(_h([100])) == 100


def test_moving_average_uses_last_window():
    assert moving_average(_h([100, 110, 130, 120]), window=3) == pytest.approx(120)


def test_moving_average_with_short_history_uses_all():
    assert moving_average(_h([100, 110]), window=3) == pytest.approx(105)


def test_baselines_registry():
    assert set(BASELINES) == {"naive", "drift", "moving_average"}
    history = _h([100, 110, 120])
    assert all(callable(model) and model(history) > 0 for model in BASELINES.values())


@pytest.mark.parametrize("model", [naive, drift, moving_average])
def test_empty_history_raises(model):
    with pytest.raises(ValueError):
        model(pd.Series([], dtype=float))
