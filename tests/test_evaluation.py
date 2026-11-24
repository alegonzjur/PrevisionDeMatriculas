"""Tests de las líneas base y de la evaluación de origen móvil (fase 3)."""

import numpy as np
import pandas as pd
import pytest

from conftest import make_panel
from prevision.evaluation import (
    BASELINES,
    add_size_tier,
    compare_to_naive,
    compute_metrics,
    drift,
    metrics_report,
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


# ------------------------------------------------------ métricas y tramos


def _forecasts(*rows):
    """Previsiones a mano: tuplas (modelo, y_true, y_pred[, target_year[, provisional]])."""
    records = []
    for row in rows:
        model, y_true, y_pred, *rest = row
        target_year = rest[0] if rest else 2024
        provisional = rest[1] if len(rest) > 1 else False
        records.append(
            {
                "series_id": "U|A",
                "origin_year": target_year - 1,
                "target_year": target_year,
                "model": model,
                "y_true": float(y_true),
                "y_pred": float(y_pred),
                "is_provisional_target": provisional,
            }
        )
    return pd.DataFrame(records, columns=FORECAST_COLUMNS)


def test_metrics_hand_computed():
    row = compute_metrics(_forecasts(("naive", 100, 150), ("naive", 300, 300))).iloc[0]
    assert row["n_pairs"] == 2
    assert row["mae"] == 25
    assert row["wape"] == pytest.approx(0.125)
    assert row["mape"] == pytest.approx(0.25)
    assert row["n_excluded_mape"] == 0


def test_zero_y_true_excluded_from_mape_and_counted():
    row = compute_metrics(_forecasts(("naive", 0, 5), ("naive", 100, 110))).iloc[0]
    assert row["mape"] == pytest.approx(0.1)
    assert row["n_excluded_mape"] == 1
    assert row["mae"] == pytest.approx(7.5)
    assert row["wape"] == pytest.approx(0.15)


def test_wape_is_nan_when_total_is_zero():
    row = compute_metrics(_forecasts(("naive", 0, 5))).iloc[0]
    assert np.isnan(row["wape"])
    assert np.isnan(row["mape"])


def test_vs_naive_relative_difference():
    forecasts = _forecasts(
        ("naive", 100, 110), ("naive", 100, 110), ("drift", 100, 120), ("drift", 100, 120)
    )
    metrics = compute_metrics(forecasts).set_index("model")
    assert metrics.loc["naive", "wape_vs_naive"] == pytest.approx(0.0)
    assert metrics.loc["drift", "wape_vs_naive"] == pytest.approx(1.0)
    assert metrics.loc["drift", "mae_vs_naive"] == pytest.approx(1.0)


def test_vs_naive_is_nan_without_naive():
    metrics = compute_metrics(_forecasts(("drift", 100, 120)))
    assert metrics["wape_vs_naive"].isna().all()


def test_group_by_target_year():
    forecasts = _forecasts(
        ("naive", 100, 110, 2023), ("naive", 100, 130, 2024), ("drift", 100, 100, 2024)
    )
    metrics = compute_metrics(forecasts, by=["target_year"])
    naive_2023 = metrics[(metrics.model == "naive") & (metrics.target_year == 2023)].iloc[0]
    naive_2024 = metrics[(metrics.model == "naive") & (metrics.target_year == 2024)].iloc[0]
    assert (naive_2023["n_pairs"], naive_2023["mae"]) == (1, 10)
    assert (naive_2024["n_pairs"], naive_2024["mae"]) == (1, 30)
    assert len(metrics) == 3
    drift_2024 = metrics[(metrics.model == "drift") & (metrics.target_year == 2024)].iloc[0]
    assert drift_2024["mae_vs_naive"] == pytest.approx(-1.0)  # error 0 frente a 30


def test_metrics_report_scopes():
    forecasts = _forecasts(
        ("naive", 100, 110, 2024), ("naive", 100, 130, 2025, True)
    )
    report = metrics_report(forecasts)
    totals = report[report["target_year"].isna()].set_index("scope")
    assert totals.loc["todos", "n_pairs"] == 2
    assert totals.loc["sin_provisional", "n_pairs"] == 1
    assert totals.loc["todos", "mae"] == 20
    assert totals.loc["sin_provisional", "mae"] == 10
    by_year = report[report["scope"] == "sin_provisional"].dropna(subset=["target_year"])
    assert by_year["target_year"].tolist() == [2024]


def test_empty_forecasts_give_empty_metrics_with_columns():
    empty = _forecasts()
    metrics = compute_metrics(empty)
    assert metrics.empty
    assert {"model", "n_pairs", "mae", "wape", "mape"} <= set(metrics.columns)
    report = metrics_report(empty)
    assert report.empty
    assert {"scope", "target_year", "model", "wape"} <= set(report.columns)


def test_add_size_tier_terciles():
    quality = pd.DataFrame(
        {"series_id": [f"U|{c}" for c in "ABCDEF"], "size_last": [10, 20, 30, 40, 50, 60]}
    )
    forecasts = pd.concat(
        [_forecasts(("naive", 100, 100)).assign(series_id=f"U|{c}") for c in "ABCDEF"],
        ignore_index=True,
    )
    result = add_size_tier(forecasts, quality)
    tiers = result.set_index("series_id")["size_tier"]
    assert tiers["U|A"] == tiers["U|B"] == "pequeño"
    assert tiers["U|C"] == tiers["U|D"] == "mediano"
    assert tiers["U|E"] == tiers["U|F"] == "grande"


def test_bias_is_mean_signed_error():
    row = compute_metrics(_forecasts(("naive", 100, 150), ("naive", 300, 270))).iloc[0]
    assert row["bias"] == pytest.approx((50 - 30) / 2)  # positivo = sobreestima


def test_compare_to_naive_counts_pairs_and_series():
    def pair(series_id, origin, model, y_pred):
        return {
            "series_id": series_id,
            "origin_year": origin,
            "target_year": origin + 1,
            "model": model,
            "y_true": 100.0,
            "y_pred": y_pred,
            "is_provisional_target": False,
        }

    rows = [
        # Serie A: la deriva mejora un par y empeora otro (MAE 12,5 frente a 10)
        pair("U|A", 2020, "naive", 110.0), pair("U|A", 2020, "drift", 105.0),
        pair("U|A", 2021, "naive", 110.0), pair("U|A", 2021, "drift", 120.0),
        # Serie B: la deriva acierta
        pair("U|B", 2020, "naive", 110.0), pair("U|B", 2020, "drift", 100.0),
    ]
    result = compare_to_naive(pd.DataFrame(rows), model="drift")
    assert result["n_pairs"] == 3
    assert result["share_pairs_better"] == pytest.approx(2 / 3)
    assert result["share_pairs_equal"] == 0
    assert result["n_series"] == 2
    assert result["n_series_better"] == 1
