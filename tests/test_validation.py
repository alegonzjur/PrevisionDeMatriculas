import pandas as pd
import pytest

from prevision.cleaning import CleaningLog, filter_nursing_degrees
from prevision.config import RAW_FILE, SHEET_CENTERS, SHEET_DEGREES
from prevision.loading import read_raw_sheet, wide_to_long
from prevision.validation import compare_university_totals

NAN = float("nan")


def long_frame(*rows):
    """Cada fila: (university, year_start, enrolled)."""
    return pd.DataFrame(rows, columns=["university", "year_start", "enrolled"])


def test_no_differences_when_totals_match():
    centers = long_frame(("Granada", 2024, 100), ("Granada", 2024, 200))
    degrees = long_frame(("Granada", 2024, 300))
    assert compare_university_totals(centers, degrees).empty


def test_reports_university_and_year_when_totals_differ():
    centers = long_frame(("Granada", 2024, 100), ("Granada", 2025, 200))
    degrees = long_frame(("Granada", 2024, 100), ("Granada", 2025, 250))
    diff = compare_university_totals(centers, degrees)
    assert len(diff) == 1
    row = diff.iloc[0]
    assert (row.university, row.year_start) == ("Granada", 2025)
    assert (row.enrolled_centers, row.enrolled_degrees) == (200, 250)


def test_all_nan_on_both_sides_is_not_a_difference():
    centers = long_frame(("Granada", 2024, NAN))
    degrees = long_frame(("Granada", 2024, NAN))
    assert compare_university_totals(centers, degrees).empty


def test_data_on_one_side_only_is_a_difference():
    centers = long_frame(("Granada", 2024, 100))
    degrees = long_frame(("Granada", 2024, NAN))
    assert len(compare_university_totals(centers, degrees)) == 1


@pytest.mark.skipif(not RAW_FILE.exists(), reason="falta el Excel real")
def test_real_university_totals_match_grado_sheet():
    log = CleaningLog()
    centers = wide_to_long(filter_nursing_degrees(read_raw_sheet(RAW_FILE, SHEET_CENTERS), log))
    degrees = wide_to_long(filter_nursing_degrees(read_raw_sheet(RAW_FILE, SHEET_DEGREES), log))
    diff = compare_university_totals(centers, degrees)
    assert diff.empty, diff.to_string()
