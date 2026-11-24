"""Tests de la calidad y elegibilidad de series (fase 2)."""

import numpy as np
import pandas as pd
import pytest

from conftest import make_panel
from prevision.linking import LINK_COLUMNS, apply_links
from prevision.quality import series_quality

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


def _series(*spans):
    """Panel de series sin enlaces. Cada tramo es (código, primer año, último año, matrícula)."""
    rows = [("U", code, y, e) for code, first, last, e in spans for y in range(first, last + 1)]
    return apply_links(make_panel(rows), pd.DataFrame(columns=LINK_COLUMNS))


def _row(quality, code):
    return quality[quality["series_id"] == f"U|{code}"].iloc[0]


def test_output_columns():
    quality = series_quality(_series(("A", 2020, 2025, 100)))
    assert list(quality.columns) == QUALITY_COLUMNS


def test_n_seasons_and_years():
    quality = series_quality(_series(("A", 2018, 2025, 100)))
    row = _row(quality, "A")
    assert row["first_year"] == 2018
    assert row["last_year"] == 2025
    assert row["n_seasons"] == 8
    assert row["size_last"] == 100
    assert row["active_last"]


def test_eligible_at_min_seasons_boundary():
    series = _series(("A", 2022, 2025, 100), ("B", 2023, 2025, 100), ("Z", 2015, 2025, 50))
    quality = series_quality(series, min_seasons=4)
    assert _row(quality, "A")["eligible"]  # exactamente 4 cursos
    assert not _row(quality, "B")["eligible"]  # uno menos


def test_series_ending_before_last_season_not_eligible():
    series = _series(("A", 2015, 2020, 100), ("Z", 2015, 2025, 50))
    row = _row(series_quality(series, min_seasons=4), "A")
    assert not row["active_last"]
    assert not row["eligible"]


def test_jump_flagged_but_data_untouched():
    series = pd.DataFrame(
        {
            "series_id": "U|A",
            "university": "U",
            "center_code_final": "A",
            "center_name": "Centro A",
            "year_start": [2024, 2025],
            "season": ["2024-2025", "2025-2026"],
            "enrolled": [100.0, 300.0],
            "pct_women": 70.0,
            "is_provisional": [False, True],
            "n_centers": 1,
            "n_source_codes": 1,
        }
    )
    snapshot = series.copy()
    row = series_quality(series, jump_ratio=1.5).iloc[0]
    assert row["n_jumps"] == 1
    assert row["max_jump_ratio"] == pytest.approx(3.0)
    pd.testing.assert_frame_equal(series, snapshot)


def test_drop_counts_as_jump():
    series = _series(("A", 2024, 2024, 200))
    series = pd.concat(
        [series, series.assign(year_start=2025, season="2025-2026", enrolled=100.0)],
        ignore_index=True,
    )
    row = series_quality(series, jump_ratio=1.5).iloc[0]
    assert row["max_jump_ratio"] == pytest.approx(2.0)
    assert row["n_jumps"] == 1


def test_small_change_is_not_a_jump():
    series = _series(("A", 2024, 2024, 100))
    series = pd.concat(
        [series, series.assign(year_start=2025, season="2025-2026", enrolled=110.0)],
        ignore_index=True,
    )
    row = series_quality(series, jump_ratio=1.5).iloc[0]
    assert row["n_jumps"] == 0
    assert row["max_jump_ratio"] == pytest.approx(1.1)


def test_nan_in_middle_creates_no_false_jump():
    series = _series(("A", 2023, 2025, 100))
    series.loc[series.year_start == 2024, "enrolled"] = np.nan
    row = series_quality(series, jump_ratio=1.5).iloc[0]
    assert row["n_jumps"] == 0
    assert np.isnan(row["max_jump_ratio"])
    assert row["n_seasons"] == 2  # solo cuentan los cursos con dato
    assert row["size_last"] == 100


def test_is_linked_from_n_source_codes():
    series = _series(("A", 2020, 2025, 100), ("B", 2020, 2025, 100))
    series.loc[series.series_id == "U|A", "n_source_codes"] = 2
    quality = series_quality(series)
    assert _row(quality, "A")["is_linked"]
    assert not _row(quality, "B")["is_linked"]
