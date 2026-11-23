import hashlib

import pandas as pd
import pytest
from conftest import build_workbook, make_row

from prevision.cleaning import CleaningLog, filter_nursing_degrees
from prevision.config import RAW_FILE, SHEET_CENTERS
from prevision.loading import read_raw_sheet
from prevision.pipeline import extract, load, run_pipeline, transform

TITLE_UGR = "Graduado o Graduada en Enfermería por la Universidad de Granada"


def fixture_rows(granada_2025_in_degrees=812):
    """Excel de prueba: Granada con dos códigos (solape en 2025) y Almería."""
    ugr = {"university": "Granada", "center_code": "18009225"}
    alm = {"university": "Almería", "center_code": "04008558"}
    centers = [
        make_row(**ugr, degree_code="2501351", values={2025: (613, 0.7), 2024: (801, 0.7), 2023: (775, 0.7)}),
        make_row(**ugr, degree_code="1500083", values={2025: (199, 0.7)}),
        make_row(**alm, degree_code="2504090", values={2025: (528, 0.8), 2024: (525, 0.8)}),
        make_row(**ugr, degree_code="9999", degree_name="Diplomado en Enfermería", values={2023: (50, 0.9)}),
    ]
    degrees = [
        make_row(
            university="Granada",
            degree_code="2501351",
            degree_name=TITLE_UGR,
            values={2025: (granada_2025_in_degrees, 0.7), 2024: (801, 0.7), 2023: (775, 0.7)},
        ),
        make_row(university="Almería", degree_code="2504090", values={2025: (528, 0.8), 2024: (525, 0.8)}),
    ]
    return centers, degrees


@pytest.fixture
def workbook(tmp_path):
    centers, degrees = fixture_rows()
    return build_workbook(tmp_path / "raw.xlsx", centers, degrees)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_run_pipeline_end_to_end_on_fixture(workbook, tmp_path):
    out = tmp_path / "processed"
    panel = run_pipeline(workbook, out)
    assert len(panel) == 6  # 2 centros x 3 cursos
    granada_2025 = panel[(panel.center_code == "18009225") & (panel.year_start == 2025)]
    assert granada_2025.iloc[0].enrolled == 812
    assert (out / "enfermeria_panel.csv").exists()
    assert (out / "cleaning_log.md").exists()
    saved = pd.read_csv(out / "enfermeria_panel.csv", dtype={"center_code": str})
    assert len(saved) == 6
    assert saved["center_code"].str.startswith("04").any()  # cero inicial conservado


def test_run_pipeline_does_not_modify_raw_file(workbook, tmp_path):
    before = sha256(workbook)
    run_pipeline(workbook, tmp_path / "processed")
    assert sha256(workbook) == before


def test_transform_log_has_one_entry_per_rule(workbook):
    centers, degrees = extract(workbook)
    _, log = transform(centers, degrees)
    rule_ids = [e["rule_id"] for e in log.entries]
    assert len(rule_ids) == len(set(rule_ids))
    assert set(rule_ids) == {"R1-nivel", "R2-titulacion", "R3-unificacion", "V1-validacion"}


def test_transform_warns_when_totals_do_not_match(tmp_path):
    centers_rows, degrees_rows = fixture_rows(granada_2025_in_degrees=900)
    path = build_workbook(tmp_path / "raw.xlsx", centers_rows, degrees_rows)
    centers, degrees = extract(path)
    with pytest.warns(UserWarning, match="totales por universidad"):
        _, log = transform(centers, degrees)
    assert any("1 diferencias" in e["description"] for e in log.entries)


def test_load_creates_output_directory(workbook, tmp_path):
    centers, degrees = extract(workbook)
    panel, log = transform(centers, degrees)
    csv_path, log_path = load(panel, log, tmp_path / "nuevo" / "subdir")
    assert csv_path.exists() and log_path.exists()


@pytest.mark.skipif(not RAW_FILE.exists(), reason="falta el Excel real")
def test_real_panel_invariants(tmp_path):
    expected_centers = len(
        filter_nursing_degrees(read_raw_sheet(RAW_FILE, SHEET_CENTERS), CleaningLog())
        .drop_duplicates(["university", "center_code"])
    )
    panel = run_pipeline(RAW_FILE, tmp_path)
    keys = panel.drop_duplicates(["university", "center_code"])
    assert len(keys) == expected_centers
    assert (panel.groupby(["university", "center_code"]).size() == 11).all()
    assert panel.year_start.between(2015, 2025).all()
    assert set(panel[panel.is_provisional].year_start) == {2025}
    assert not panel.duplicated(["university", "center_code", "year_start"]).any()
    assert (panel.enrolled.dropna() >= 0).all()
    sevilla = panel[(panel.university == "Sevilla") & (panel.center_code == "41015500")]
    comillas = panel[(panel.university == "Pontificia Comillas") & (panel.center_code == "28042772")]
    assert len(sevilla) == 11 and len(comillas) == 11  # dos series distintas
