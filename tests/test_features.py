"""Tests de las variables y los ejemplos de entrenamiento de los modelos globales (fase 4)."""

import numpy as np
import pandas as pd
import pytest

from prevision.features import (
    FEATURE_SETS,
    build_examples,
    build_prediction_rows,
)


def make_table(spec):
    """Tabla de series a mano. `spec`: {series_id: (región, {año: matrícula})}."""
    rows = []
    for series_id, (region, values) in spec.items():
        for year, enrolled in values.items():
            rows.append(
                {
                    "series_id": series_id,
                    "year_start": year,
                    "enrolled": enrolled,
                    "pct_women": 0.8,
                    "region": region,
                    "is_provisional": False,
                }
            )
    return pd.DataFrame(rows)


def years(first, *values):
    """{año: valor} con años consecutivos desde `first`."""
    return {first + i: v for i, v in enumerate(values)}


def row(frame, series_id, origin):
    selected = frame[(frame.series_id == series_id) & (frame.origin_year == origin)]
    assert len(selected) == 1
    return selected.iloc[0]


def test_feature_sets_are_nested_as_designed():
    base = FEATURE_SETS["base"]
    assert base == ["g1", "g2", "drift_rel", "log_size", "n_seasons", "pct_women", "system_growth"]
    assert FEATURE_SETS["with_region"] == base + ["region_growth"]
    assert FEATURE_SETS["without_system"] == [c for c in base if c != "system_growth"]


def test_features_of_known_series():
    table = make_table({"A": ("R", years(2018, 100, 110, 121, 133.1))})
    prediction = build_prediction_rows(table, origin=2021)
    r = row(prediction, "A", 2021)
    assert r.g1 == pytest.approx(np.log(1.1))
    assert r.g2 == pytest.approx(np.log(1.1))
    assert r.log_size == pytest.approx(np.log(133.1))
    assert r.n_seasons == 4
    assert r.last_value == pytest.approx(133.1)
    assert r.drift_rel == pytest.approx(((133.1 - 100) / 3) / 133.1)
    assert r.pct_women == pytest.approx(0.8)
    assert "target" not in prediction.columns


def test_target_is_log_growth_to_next_season():
    table = make_table({"A": ("R", years(2018, 100, 110, 121, 133.1))})
    examples = build_examples(table, up_to=2021)
    # Solo el origen 2020 tiene a la vez 3 cursos de historia y curso siguiente.
    assert examples["origin_year"].tolist() == [2020]
    assert examples.iloc[0].target == pytest.approx(np.log(133.1 / 121))


def test_system_growth_excludes_own_series():
    table = make_table(
        {
            "A": ("R", years(2018, 100, 110, 121, 133.1)),  # g1 = ln 1,10
            "B": ("R", years(2018, 100, 100, 120, 120)),  # g1 = ln 1,00 = 0
            "C": ("R", years(2018, 100, 100, 100, 150)),  # g1 = ln 1,50
        }
    )
    prediction = build_prediction_rows(table, origin=2021)
    g1 = {"A": np.log(1.1), "B": 0.0, "C": np.log(1.5)}
    for own, others in (("A", ("B", "C")), ("B", ("A", "C")), ("C", ("A", "B"))):
        expected = np.mean([g1[o] for o in others])
        assert row(prediction, own, 2021).system_growth == pytest.approx(expected)


def test_system_growth_is_nan_without_other_series():
    table = make_table({"A": ("R", years(2018, 100, 110, 121, 133.1))})
    assert np.isnan(row(build_prediction_rows(table, origin=2021), "A", 2021).system_growth)


def test_region_growth_needs_two_other_series():
    table = make_table(
        {
            "A": ("R1", years(2018, 100, 110, 121, 133.1)),
            "B": ("R1", years(2018, 100, 100, 100, 120)),  # única otra en R1
            "C": ("R2", years(2018, 100, 100, 100, 150)),
            "D": ("R2", years(2018, 100, 100, 100, 100)),
            "E": ("R2", years(2018, 100, 100, 100, 130)),
        }
    )
    prediction = build_prediction_rows(table, origin=2021)
    # R1: A y B solo tienen una "otra" serie en la región -> vacío.
    assert np.isnan(row(prediction, "A", 2021).region_growth)
    assert np.isnan(row(prediction, "B", 2021).region_growth)
    # R2: C tiene dos otras (D, E) -> su media.
    assert row(prediction, "C", 2021).region_growth == pytest.approx(
        np.mean([np.log(1.0), np.log(1.3)])
    )


def test_examples_only_use_targets_up_to_cutoff():
    table = make_table(
        {
            "A": ("R", years(2015, 100, 102, 104, 106, 108, 110, 112)),
            "B": ("R", years(2015, 50, 52, 54, 56, 58, 60, 62)),
        }
    )
    examples = build_examples(table, up_to=2020)
    assert not examples.empty
    assert (examples["origin_year"] + 1 <= 2020).all()
    assert examples["origin_year"].max() == 2019


def test_gap_in_years_creates_no_example():
    # Sin dato en 2019: el origen 2018 no tiene curso siguiente consecutivo y 2019 no existe.
    table = make_table({"A": ("R", {2016: 100, 2017: 105, 2018: 110, 2020: 120, 2021: 125, 2022: 130})})
    examples = build_examples(table, up_to=2022)
    assert 2018 not in examples["origin_year"].tolist()
    assert 2019 not in examples["origin_year"].tolist()
    assert 2020 in examples["origin_year"].tolist()
    assert examples.notna().all().drop(["pct_women", "system_growth", "region_growth"]).all()


def test_non_positive_enrollment_raises_naming_the_series():
    table = make_table(
        {
            "A": ("R", years(2018, 100, 110, 121, 133.1)),
            "Mala|1": ("R", years(2018, 100, 0, 90, 95)),
        }
    )
    with pytest.raises(ValueError, match=r"Mala\|1"):
        build_examples(table, up_to=2021)
    with pytest.raises(ValueError, match=r"Mala\|1"):
        build_prediction_rows(table, origin=2021)


def test_prediction_rows_ignore_later_data():
    base = {
        "A": ("R", years(2016, 100, 104, 108, 112, 116, 120)),
        "B": ("R", years(2016, 50, 51, 53, 54, 56, 57)),
        "C": ("R", years(2016, 80, 80, 82, 83, 85, 90)),
        "Corta": ("R", years(2020, 10, 12)),  # menos de 3 cursos: sin fila
    }
    table = make_table(base)
    shifted = table.copy()
    later = shifted["year_start"] > 2019
    shifted.loc[later, "enrolled"] = shifted.loc[later, "enrolled"] * 10
    before = build_prediction_rows(table, origin=2019)
    after = build_prediction_rows(shifted, origin=2019)
    pd.testing.assert_frame_equal(before, after)
    assert sorted(before["series_id"]) == ["A", "B", "C"]


def test_examples_ignore_data_after_cutoff():
    table = make_table(
        {
            "A": ("R", years(2016, 100, 104, 108, 112, 116, 120)),
            "B": ("R", years(2016, 50, 51, 53, 54, 56, 57)),
        }
    )
    shifted = table.copy()
    later = shifted["year_start"] > 2019
    shifted.loc[later, "enrolled"] = shifted.loc[later, "enrolled"] * 10
    pd.testing.assert_frame_equal(
        build_examples(table, up_to=2019), build_examples(shifted, up_to=2019)
    )
