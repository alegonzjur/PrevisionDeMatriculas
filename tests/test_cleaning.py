import pandas as pd
import pytest

from prevision.cleaning import CleaningLog, filter_nursing_degrees
from prevision.config import RAW_FILE, SHEET_CENTERS
from prevision.loading import read_raw_sheet

GRADO = "Grado y 1º y 2º ciclo"


def wide_frame(*rows):
    """DataFrame ancho mínimo: cada fila es (level, degree_name)."""
    return pd.DataFrame(rows, columns=["level", "degree_name"])


def apply_filter(*rows):
    log = CleaningLog()
    return filter_nursing_degrees(wide_frame(*rows), log), log


def test_keeps_literal_title():
    result, _ = apply_filter((GRADO, "Graduado o Graduada en Enfermería"))
    assert len(result) == 1


def test_keeps_title_with_university_suffix():
    title = "Graduado o Graduada en Enfermería por la Universidad de Granada"
    result, _ = apply_filter((GRADO, title))
    assert len(result) == 1


def test_drops_diplomado():
    result, _ = apply_filter((GRADO, "Diplomado en Enfermería"))
    assert result.empty


def test_drops_pceo_double_degrees():
    result, _ = apply_filter(
        (GRADO, "PCEO Grado en Fisioterapia / Grado en Enfermería"),
        (GRADO, "PCEO Grado en Enfermería / Grado en Nutrición Humana y Dietética"),
    )
    assert result.empty


def test_drops_master_and_doctorate_titles():
    result, _ = apply_filter(
        (GRADO, "Máster Universitario en Enfermería Oftalmológica por la Universidad de Valladolid"),
        (GRADO, "Programa de Doctorado en Enfermería y Salud por la Universidad de Barcelona"),
    )
    assert result.empty


def test_drops_non_grado_level():
    result, _ = apply_filter(("Máster", "Graduado o Graduada en Enfermería"))
    assert result.empty


def test_log_records_rows_before_and_after():
    result, log = apply_filter(
        (GRADO, "Graduado o Graduada en Enfermería"),
        (GRADO, "Diplomado en Enfermería"),
        ("Máster", "Graduado o Graduada en Enfermería"),
        (GRADO, "Graduado o Graduada en Fisioterapia"),
    )
    assert len(log.entries) == 2  # una entrada por regla (nivel y titulación)
    assert log.entries[0]["before"] == 4
    assert log.entries[-1]["after"] == len(result) == 1
    dropped = sum(e["before"] - e["after"] for e in log.entries)
    assert dropped == 3


def test_log_to_markdown_contains_rule_ids():
    _, log = apply_filter((GRADO, "Graduado o Graduada en Enfermería"))
    markdown = log.to_markdown()
    for entry in log.entries:
        assert entry["rule_id"] in markdown


@pytest.mark.skipif(not RAW_FILE.exists(), reason="falta el Excel real")
def test_real_filter_gives_158_rows():
    wide = read_raw_sheet(RAW_FILE, SHEET_CENTERS)
    result = filter_nursing_degrees(wide, CleaningLog())
    assert len(result) == 158
