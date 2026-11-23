import pandas as pd
import pytest
from conftest import build_workbook, make_row
from openpyxl import load_workbook

from prevision.config import RAW_FILE, SHEET_CENTERS
from prevision.loading import read_raw_sheet, wide_to_long


@pytest.fixture
def workbook(tmp_path):
    centers = [
        make_row(
            university="Almería",
            center_code="04008558",
            values={2025: (528, 0.8), 2024: (525, 0.75), 2023: (None, None)},
        ),
        make_row(
            university="Granada",
            values={2025: (613, 0.7), 2024: (801, 0.72), 2023: (775, 0.74)},
        ),
    ]
    return build_workbook(tmp_path / "raw.xlsx", centers, [])


def test_read_raw_sheet_names_columns_and_keeps_codes_as_text(workbook):
    wide = read_raw_sheet(workbook, SHEET_CENTERS)
    assert wide.loc[0, "center_code"] == "04008558"  # cero inicial conservado
    assert "enrolled_2025" in wide.columns
    assert "pct_women_2024" in wide.columns
    assert wide.loc[0, "university"] == "Almería"


def test_read_raw_sheet_keeps_nan_not_zero(workbook):
    wide = read_raw_sheet(workbook, SHEET_CENTERS)
    assert pd.isna(wide.loc[0, "enrolled_2023"])
    assert wide.loc[0, "enrolled_2025"] == 528


def test_read_raw_sheet_ignores_trailing_empty_rows(tmp_path):
    path = build_workbook(
        tmp_path / "raw.xlsx", [make_row(values={2025: (10, 0.5)})], [], trailing_empty_rows=3
    )
    assert len(read_raw_sheet(path, SHEET_CENTERS)) == 1


def test_read_raw_sheet_rejects_unknown_header(workbook):
    wb = load_workbook(workbook)
    wb[SHEET_CENTERS]["A4"] = "Columna rara"
    wb.save(workbook)
    with pytest.raises(ValueError):
        read_raw_sheet(workbook, SHEET_CENTERS)


def test_wide_to_long_season_and_provisional(workbook):
    long = wide_to_long(read_raw_sheet(workbook, SHEET_CENTERS))
    seasons = long.drop_duplicates("year_start").set_index("year_start")
    assert seasons.loc[2024, "season"] == "2024-2025"
    assert seasons.loc[2025, "is_provisional"]
    assert not seasons.loc[2024, "is_provisional"]
    assert not seasons.loc[2023, "is_provisional"]


def test_wide_to_long_flags_only_the_latest_season_as_provisional(tmp_path):
    # Tras una actualización de datos (llega 2026-27), el provisional es el último curso.
    path = build_workbook(
        tmp_path / "raw.xlsx",
        [make_row(values={2026: (10, 0.5), 2025: (9, 0.5), 2024: (8, 0.5)})],
        [],
        years=(2026, 2025, 2024),
    )
    long = wide_to_long(read_raw_sheet(path, SHEET_CENTERS))
    provisional = long.loc[long["is_provisional"], "year_start"].unique().tolist()
    assert provisional == [2026]


def test_wide_to_long_row_count(workbook):
    wide = read_raw_sheet(workbook, SHEET_CENTERS)
    long = wide_to_long(wide)
    assert len(long) == len(wide) * 3  # tres cursos en el Excel de prueba
    assert {"enrolled", "pct_women", "year_start"} <= set(long.columns)


@pytest.mark.skipif(not RAW_FILE.exists(), reason="falta el Excel real")
def test_real_centers_sheet_has_11_seasons():
    wide = read_raw_sheet(RAW_FILE, SHEET_CENTERS)
    years = sorted(int(c.split("_")[1]) for c in wide.columns if c.startswith("enrolled_"))
    assert years == list(range(2015, 2026))
