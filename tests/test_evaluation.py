"""Tests de las líneas base y de la evaluación de origen móvil (fase 3)."""

import numpy as np
import pandas as pd
import pytest

from conftest import make_panel
from prevision.evaluation import (
    BASELINES,
    drift,
    moving_average,
    naive,
    rolling_origin_forecasts,
)
from prevision.linking import LINK_COLUMNS, apply_links

FORECAST_COLUMNS = [
    "series_id",
    "origin_year",
    "target_year",
    "model",
    "y_true",
    "y_pred",
    "is_provisional_target",
]


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


# ------------------------------------------------- rolling_origin_forecasts


def _series(first=2015, last=2025, code="A"):
    """Una serie con matrícula 100 + 10 * (año - 2015), sin enlaces."""
    rows = [("U", code, y, 100.0 + 10 * (y - 2015)) for y in range(first, last + 1)]
    return apply_links(make_panel(rows), pd.DataFrame(columns=LINK_COLUMNS))


def test_pair_count_for_complete_series():
    result = rolling_origin_forecasts(_series(), min_train=4)
    assert len(result) == 7 * 3  # orígenes 2018-2024 x tres modelos
    assert sorted(result["target_year"].unique()) == list(range(2019, 2026))
    assert list(result.columns) == FORECAST_COLUMNS


def test_short_series_gives_no_pairs():
    assert rolling_origin_forecasts(_series(2015, 2018), min_train=4).empty
    five = rolling_origin_forecasts(_series(2015, 2019), min_train=4)
    assert len(five) == 3  # un par por modelo
    assert five["target_year"].unique().tolist() == [2019]


def test_nan_target_drops_pair_and_nan_origin_is_skipped():
    series = _series()
    series.loc[series.year_start == 2020, "enrolled"] = np.nan
    result = rolling_origin_forecasts(series, min_train=4)
    per_model = result[result["model"] == "naive"]
    assert per_model["target_year"].tolist() == [2019, 2022, 2023, 2024, 2025]
    # Origen 2021: la historia salta el curso 2020 (NaN) y el ingenuo usa el valor de 2021.
    row = per_model[per_model.target_year == 2022].iloc[0]
    assert (row["origin_year"], row["y_pred"], row["y_true"]) == (2021, 160, 170)


def test_naive_values():
    result = rolling_origin_forecasts(_series(), min_train=4)
    row = result[(result.model == "naive") & (result.target_year == 2021)].iloc[0]
    assert row["origin_year"] == 2020
    assert row["y_pred"] == 150
    assert row["y_true"] == 160


def test_provisional_flag_on_last_target():
    result = rolling_origin_forecasts(_series(), min_train=4)
    flagged = result.loc[result["is_provisional_target"], "target_year"].unique()
    assert flagged.tolist() == [2025]


def test_custom_model_is_used():
    result = rolling_origin_forecasts(_series(), models={"zero": lambda h: 0.0})
    assert result["model"].unique().tolist() == ["zero"]
    assert (result["y_pred"] == 0).all()


def test_no_leakage_future_changes_do_not_alter_past_forecasts():
    series = _series()
    before = rolling_origin_forecasts(series, min_train=4)
    altered = series.copy()
    altered.loc[altered.year_start > 2021, "enrolled"] *= 10
    after = rolling_origin_forecasts(altered, min_train=4)
    keys = ["series_id", "origin_year", "model"]
    merged = before.merge(after, on=keys, suffixes=("_before", "_after"))
    past = merged[merged["origin_year"] <= 2021]
    assert len(past) == 4 * 3  # orígenes 2018-2021 x tres modelos
    pd.testing.assert_series_equal(
        past["y_pred_before"], past["y_pred_after"], check_names=False
    )


def test_unsorted_input_gives_same_result():
    series = pd.concat([_series(code="A"), _series(2017, 2025, code="B")], ignore_index=True)
    order = ["series_id", "origin_year", "model"]
    expected = rolling_origin_forecasts(series).sort_values(order).reset_index(drop=True)
    shuffled = series.sample(frac=1, random_state=0)
    result = rolling_origin_forecasts(shuffled).sort_values(order).reset_index(drop=True)
    pd.testing.assert_frame_equal(result, expected)


def test_empty_input_returns_empty_frame_with_columns():
    result = rolling_origin_forecasts(_series().iloc[0:0])
    assert result.empty
    assert list(result.columns) == FORECAST_COLUMNS
