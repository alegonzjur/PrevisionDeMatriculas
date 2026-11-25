import pandas as pd
import pytest

from prevision.cleaning import CleaningLog, filter_nursing_degrees, unify_center_series
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


# --- Unificación de series por centro -------------------------------------------


def long_frame(*rows):
    """Formato largo mínimo. Cada fila: (university, center_code, center_name,
    degree_code, year_start, enrolled, pct_women)."""
    df = pd.DataFrame(
        rows,
        columns=[
            "university",
            "center_code",
            "center_name",
            "degree_code",
            "year_start",
            "enrolled",
            "pct_women",
        ],
    )
    df["region"] = "Andalucía"
    df["season"] = df["year_start"].map(lambda y: f"{y}-{y + 1}")
    df["is_provisional"] = df["year_start"] == 2025
    return df


NAN = float("nan")
GRANADA = ("Granada", "18009225", "Facultad de Ciencias de la Salud")


def unify(*rows):
    log = CleaningLog()
    return unify_center_series(long_frame(*rows), log), log


def value(panel, university, center_code, year):
    row = panel[
        (panel.university == university)
        & (panel.center_code == center_code)
        & (panel.year_start == year)
    ]
    assert len(row) == 1
    return row.iloc[0]


def test_unify_sums_codes_without_overlap():
    # Almería: un código hasta 2023 y otro desde 2025 (sin solape).
    alm = ("Almería", "04008558", "Facultad de Ciencias de la Salud")
    panel, _ = unify(
        (*alm, "2501129", 2023, 552, 0.8),
        (*alm, "2501129", 2025, NAN, NAN),
        (*alm, "2504090", 2023, NAN, NAN),
        (*alm, "2504090", 2025, 528, 0.8),
    )
    assert value(panel, "Almería", "04008558", 2023).enrolled == 552
    assert value(panel, "Almería", "04008558", 2025).enrolled == 528


def test_unify_sums_codes_with_overlap():
    # Granada 2025: plan antiguo 199 + plan nuevo 613 conviven.
    panel, log = unify(
        (*GRANADA, "1500083", 2025, 199, 0.7),
        (*GRANADA, "2501351", 2025, 613, 0.7),
        (*GRANADA, "1500083", 2024, NAN, NAN),
        (*GRANADA, "2501351", 2024, 801, 0.7),
    )
    assert value(panel, "Granada", "18009225", 2025).enrolled == 812
    assert value(panel, "Granada", "18009225", 2024).enrolled == 801
    assert "1 celdas centro-curso con solape" in log.entries[-1]["description"]


def test_unify_all_nan_stays_nan():
    panel, _ = unify(
        (*GRANADA, "1500083", 2024, NAN, NAN),
        (*GRANADA, "2501351", 2024, NAN, NAN),
    )
    assert pd.isna(value(panel, "Granada", "18009225", 2024).enrolled)


def test_unify_same_code_different_name_gives_one_series_with_latest_name():
    old = ("Granada", "52000452", "Facultad de Ciencias de la Salud de Melilla")
    new = ("Granada", "52000452", "Facultad de Enfermería de Melilla")
    panel, _ = unify(
        (*old, "1500083", 2023, 114, 0.7),
        (*old, "1500083", 2025, NAN, NAN),
        (*new, "2501351", 2023, NAN, NAN),
        (*new, "2501351", 2025, 272, 0.7),
    )
    melilla = panel[panel.center_code == "52000452"]
    assert len(melilla) == 2  # una fila por curso: una sola serie
    assert set(melilla.center_name) == {"Facultad de Enfermería de Melilla"}


def test_unify_weighted_pct_women():
    panel, _ = unify(
        (*GRANADA, "1500083", 2024, 100, 0.5),
        (*GRANADA, "2501351", 2024, 300, 0.9),
    )
    assert value(panel, "Granada", "18009225", 2024).pct_women == pytest.approx(0.8)


def test_unify_output_is_unique_per_center_and_year():
    panel, _ = unify(
        (*GRANADA, "1500083", 2024, 100, 0.5),
        (*GRANADA, "2501351", 2024, 300, 0.9),
        (*GRANADA, "1500083", 2025, NAN, NAN),
        (*GRANADA, "2501351", 2025, 613, 0.7),
    )
    assert not panel.duplicated(["university", "center_code", "year_start"]).any()
    assert list(panel.columns) == [
        "university",
        "center_code",
        "center_name",
        "region",
        "year_start",
        "season",
        "enrolled",
        "pct_women",
        "is_provisional",
    ]


def test_unify_has_no_zero_filled_missing():
    panel, _ = unify(
        (*GRANADA, "2501351", 2024, NAN, NAN),
        (*GRANADA, "2501351", 2025, 613, 0.7),
    )
    assert (panel.enrolled.fillna(-1) != 0).all()
    assert panel.enrolled.isna().sum() == 1


def test_unify_keeps_sevilla_and_comillas_san_juan_de_dios_separate():
    sevilla = ("Sevilla", "41015500", "Centro de Enfermería San Juan de Dios")
    comillas = (
        "Pontificia Comillas",
        "28042772",
        "Escuela Universitaria de Enfermería y Fisioterapia San Juan de Dios",
    )
    panel, _ = unify(
        (*sevilla, "2501190", 2025, 67, 0.8),
        (*comillas, "2500604", 2025, 1195, 0.8),
    )
    assert value(panel, "Sevilla", "41015500", 2025).enrolled == 67
    assert value(panel, "Pontificia Comillas", "28042772", 2025).enrolled == 1195


def test_panel_keeps_region():
    # La región (CCAA del SIIU) pasa al panel y es constante por centro.
    sevilla = ("Sevilla", "41015500", "Centro de Enfermería San Juan de Dios")
    long = long_frame(
        (*GRANADA, "1500083", 2024, 100, 0.5),
        (*GRANADA, "2501351", 2024, 300, 0.9),
        (*sevilla, "2500001", 2024, 50, 0.8),
    )
    long.loc[long.university == "Sevilla", "region"] = "Andalucía (Sevilla)"
    panel = unify_center_series(long, CleaningLog())
    assert panel.groupby(["university", "center_code"])["region"].nunique().eq(1).all()
    assert value(panel, "Granada", "18009225", 2024).region == "Andalucía"
    assert value(panel, "Sevilla", "41015500", 2024).region == "Andalucía (Sevilla)"


def test_unify_rejects_center_with_two_regions():
    long = long_frame(
        (*GRANADA, "1500083", 2024, 100, 0.5),
        (*GRANADA, "2501351", 2024, 300, 0.9),
    )
    long.loc[long.degree_code == "1500083", "region"] = "Otra región"
    with pytest.raises(ValueError, match="más de una región"):
        unify_center_series(long, CleaningLog())
