"""Tests del marco de origen móvil para modelos globales (fase 4)."""

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

import prevision.evaluation as evaluation
from prevision.config import MIN_TRAIN_EXAMPLES, RECENT_TARGET_FROM
from prevision.evaluation import (
    FORECAST_COLUMNS,
    GLOBAL_MODELS,
    add_region,
    naive,
    recent_metrics,
    rolling_origin_forecasts,
    rolling_origin_global,
)

KEYS = ["series_id", "origin_year"]
FIRST, LAST = 2010, 2021


def make_global_table(n_series=40, first=FIRST, last=LAST, seed=0):
    """Tabla de series sintética. El primer origen tiene un ejemplo por serie: 40 superan MIN_TRAIN_EXAMPLES."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_series):
        value = rng.uniform(80, 600)
        trend = rng.normal(0.02, 0.03)
        for year in range(first, last + 1):
            rows.append(
                {
                    "series_id": f"S{i:02d}",
                    "year_start": year,
                    "enrolled": value,
                    "pct_women": rng.uniform(0.7, 0.9),
                    "region": f"R{i % 4}",
                    "is_provisional": year == last,
                }
            )
            value *= np.exp(trend + rng.normal(0, 0.04))
    return pd.DataFrame(rows)


def scale_after(table, origin, factor=10.0):
    """Copia de la tabla con la matrícula de los cursos posteriores a `origin` multiplicada."""
    shifted = table.copy()
    later = shifted["year_start"] > origin
    shifted.loc[later, "enrolled"] = shifted.loc[later, "enrolled"] * factor
    return shifted


def test_global_models_registry():
    assert set(GLOBAL_MODELS) == {
        "ridge", "gbm", "ridge_region", "gbm_region", "ridge_no_system", "gbm_no_system",
    }
    assert GLOBAL_MODELS["ridge"][1] == GLOBAL_MODELS["gbm"][1] == "base"
    assert GLOBAL_MODELS["gbm_region"][1] == "with_region"
    assert GLOBAL_MODELS["ridge_no_system"][1] == "without_system"


def test_global_pairs_equal_baseline_pairs():
    table = make_global_table()
    # Una serie con un hueco (sin 2015): el par que cruza el hueco no existe en ningún marco.
    table = table[~((table.series_id == "S03") & (table.year_start == 2015))]
    result = rolling_origin_global(table)
    baseline = rolling_origin_forecasts(table)
    assert list(result.columns) == FORECAST_COLUMNS
    for name in GLOBAL_MODELS:
        got = result[result.model == name].sort_values(KEYS).reset_index(drop=True)
        expected = baseline[baseline.model == "naive"].sort_values(KEYS).reset_index(drop=True)
        assert len(got) == len(expected) > 0
        pd.testing.assert_frame_equal(
            got[KEYS + ["target_year", "y_true", "is_provisional_target"]],
            expected[KEYS + ["target_year", "y_true", "is_provisional_target"]],
        )


def test_zero_growth_model_reproduces_naive():
    table = make_global_table()
    zero = {"zero": (lambda: DummyRegressor(strategy="constant", constant=0.0), "base")}
    result = rolling_origin_global(table, models=zero)
    naive_forecasts = rolling_origin_forecasts(table, models={"naive": naive})
    merged = result.merge(naive_forecasts, on=KEYS, suffixes=("_zero", "_naive"))
    assert len(merged) == len(result) == len(naive_forecasts)
    np.testing.assert_allclose(merged["y_pred_zero"], merged["y_pred_naive"], rtol=1e-12)


def test_no_leak_into_global_models():
    table = make_global_table()
    models = {k: GLOBAL_MODELS[k] for k in ("ridge", "gbm", "ridge_region", "gbm_region")}
    origin = 2016
    before = rolling_origin_global(table, models=models)
    after = rolling_origin_global(scale_after(table, origin), models=models)
    before = before[before.origin_year <= origin].sort_values(KEYS + ["model"])
    after = after[after.origin_year <= origin].sort_values(KEYS + ["model"])
    assert len(before) > 0
    np.testing.assert_array_equal(before["y_pred"].to_numpy(), after["y_pred"].to_numpy())


def test_training_never_uses_targets_after_origin(monkeypatch):
    calls = []
    original = evaluation.build_examples

    def spy(series, up_to):
        examples = original(series, up_to)
        calls.append((up_to, examples))
        return examples

    monkeypatch.setattr(evaluation, "build_examples", spy)
    result = rolling_origin_global(make_global_table(), models={"ridge": GLOBAL_MODELS["ridge"]})
    assert calls
    for up_to, examples in calls:
        assert len(examples) >= MIN_TRAIN_EXAMPLES
        assert (examples["origin_year"] + 1 <= up_to).all()
    # Se entrena una vez por origen con pares, con up_to igual al origen.
    assert sorted(up_to for up_to, _ in calls) == sorted(result["origin_year"].unique())


def test_fit_is_deterministic():
    table = make_global_table()
    first = rolling_origin_global(table)
    second = rolling_origin_global(table)
    np.testing.assert_array_equal(first["y_pred"].to_numpy(), second["y_pred"].to_numpy())


def test_too_few_training_examples_raises():
    # Tres series: el primer origen tiene muy pocos ejemplos (foco 4).
    table = make_global_table(n_series=3)
    with pytest.raises(ValueError, match="ejemplos de entrenamiento"):
        rolling_origin_global(table)


def test_series_with_exactly_four_seasons_gives_no_pairs_and_no_error():
    table = make_global_table()
    short = make_global_table(n_series=1, first=LAST - 3, last=LAST, seed=7)
    short["series_id"] = "CORTA"
    result = rolling_origin_global(pd.concat([table, short], ignore_index=True))
    assert "CORTA" not in set(result["series_id"])
    assert len(result) > 0
    assert np.isfinite(result["y_pred"]).all()


def test_models_tolerate_missing_region_growth():
    # Región "SOLA" con una única serie: su region_growth es NaN (foco 2).
    table = make_global_table()
    table.loc[table.series_id == "S00", "region"] = "SOLA"
    models = {k: GLOBAL_MODELS[k] for k in ("ridge_region", "gbm_region")}
    result = rolling_origin_global(table, models=models)
    solo = result[result.series_id == "S00"]
    assert len(solo) > 0
    assert np.isfinite(solo["y_pred"]).all()
    assert np.isfinite(result["y_pred"]).all()


def test_predictions_are_positive_and_finite_for_all_models():
    result = rolling_origin_global(make_global_table())
    assert np.isfinite(result["y_pred"]).all()
    assert (result["y_pred"] > 0).all()
    assert set(result["model"]) == set(GLOBAL_MODELS)


# --- Funciones de informe (tarea 5) ------------------------------------------------------------


def test_recent_metrics_filters_target_year():
    forecasts = rolling_origin_global(
        make_global_table(), models={"ridge": GLOBAL_MODELS["ridge"]}
    )
    forecasts = pd.concat(
        [forecasts, rolling_origin_forecasts(make_global_table(), models={"naive": naive})],
        ignore_index=True,
    )
    recent = recent_metrics(forecasts, first_target_year=2018)
    subset = forecasts[forecasts["target_year"] >= 2018]
    expected_pairs = subset.groupby("model").size()
    assert recent.set_index("model")["n_pairs"].to_dict() == expected_pairs.to_dict()
    assert (recent.set_index("model").loc["naive", "wape_vs_naive"]) == 0
    # Con el corte por defecto solo cuentan los objetivos desde RECENT_TARGET_FROM.
    default = recent_metrics(forecasts)
    assert default.set_index("model")["n_pairs"].to_dict() == (
        forecasts[forecasts["target_year"] >= RECENT_TARGET_FROM].groupby("model").size().to_dict()
    )


def test_add_region_by_series():
    table = make_global_table()
    forecasts = rolling_origin_global(table, models={"ridge": GLOBAL_MODELS["ridge"]})
    with_region = add_region(forecasts, table)
    assert with_region["region"].notna().all()
    expected = table.drop_duplicates("series_id").set_index("series_id")["region"]
    assert (with_region["region"] == with_region["series_id"].map(expected)).all()
    assert len(with_region) == len(forecasts)
