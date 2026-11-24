"""Tests de la detección y aplicación de enlaces de códigos de centro (fase 2)."""

import numpy as np
import pandas as pd
import pytest

from conftest import make_panel
from prevision.linking import (
    LINK_COLUMNS,
    apply_links,
    detect_candidates,
    load_links,
)

COLUMNS = [
    "university",
    "from_center_code",
    "from_center_name",
    "to_center_code",
    "to_center_name",
    "from_last_year",
    "to_first_year",
    "from_last_enrolled",
    "to_first_enrolled",
    "size_ratio",
    "ambiguous",
]


def _span(university, code, first, last, enrolled):
    """Serie continua de un centro entre dos años, con matrícula constante."""
    return [(university, code, y, enrolled) for y in range(first, last + 1)]


def _anchor(last=2025):
    """Centro 'Z' de otra universidad que fija el último curso del panel."""
    return _span("Anclada", "Z", 2015, last, 50)


def test_detects_simple_succession():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100) + _span("U", "B", 2021, 2025, 110) + _anchor()
    )
    result = detect_candidates(panel)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["from_center_code"] == "A"
    assert row["to_center_code"] == "B"
    assert row["from_last_year"] == 2020
    assert row["to_first_year"] == 2021
    assert row["size_ratio"] == pytest.approx(1.1)
    assert not row["ambiguous"]


def test_candidate_when_b_starts_same_year_a_ends():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100) + _span("U", "B", 2020, 2025, 110) + _anchor()
    )
    result = detect_candidates(panel)
    assert len(result) == 1
    assert result.iloc[0]["to_first_year"] == 2020


def test_b_two_years_after_is_not_candidate():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100) + _span("U", "B", 2022, 2025, 110) + _anchor()
    )
    assert detect_candidates(panel).empty


def test_other_university_not_candidate():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100) + _span("V", "B", 2021, 2025, 110) + _anchor()
    )
    assert detect_candidates(panel).empty


def test_active_center_has_no_successor():
    # A llega al último curso: no puede ser origen de un enlace.
    panel = make_panel(
        _span("U", "A", 2015, 2025, 100) + _span("U", "B", 2021, 2025, 110)
    )
    assert detect_candidates(panel).empty


def test_ambiguous_flagged_when_a_has_two_successors():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100)
        + _span("U", "B", 2021, 2025, 60)
        + _span("U", "C", 2021, 2025, 50)
        + _anchor()
    )
    result = detect_candidates(panel)
    assert len(result) == 2
    assert result["ambiguous"].all()


def test_ambiguous_flagged_when_b_has_two_predecessors():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 60)
        + _span("U", "C", 2015, 2020, 50)
        + _span("U", "B", 2021, 2025, 110)
        + _anchor()
    )
    result = detect_candidates(panel)
    assert len(result) == 2
    assert result["ambiguous"].all()


def test_no_candidates_returns_empty_frame_with_columns():
    panel = make_panel(_span("U", "A", 2015, 2025, 100))
    result = detect_candidates(panel)
    assert result.empty
    assert list(result.columns) == COLUMNS


def test_nan_padding_rows_do_not_hide_succession():
    # El panel real es rectangular: los cursos sin dato son filas con matrícula NaN.
    rows = (
        [("U", "A", y, 100.0 if y <= 2020 else np.nan) for y in range(2015, 2026)]
        + [("U", "B", y, 110.0 if y >= 2021 else np.nan) for y in range(2015, 2026)]
        + _anchor()
    )
    result = detect_candidates(make_panel(rows))
    assert len(result) == 1
    row = result.iloc[0]
    assert (row["from_center_code"], row["to_center_code"]) == ("A", "B")
    assert row["from_last_year"] == 2020
    assert row["to_first_year"] == 2021
    assert row["from_last_enrolled"] == 100
    assert row["to_first_enrolled"] == 110


def test_center_without_any_data_is_ignored():
    rows = [("U", "A", y, np.nan) for y in range(2015, 2026)] + _anchor()
    assert detect_candidates(make_panel(rows)).empty


# ---------------------------------------------------------------- load_links


def test_load_links_keeps_leading_zeros(tmp_path):
    path = tmp_path / "links.csv"
    path.write_text(
        "university,from_center_code,to_center_code,decision,note\n"
        "U,01234,05678,sí,cambio de código\n",
        encoding="utf-8",
    )
    links = load_links(path)
    assert links.loc[0, "from_center_code"] == "01234"
    assert links.loc[0, "to_center_code"] == "05678"
    assert links.loc[0, "decision"] == "sí"


def test_load_links_missing_file_returns_empty_with_columns(tmp_path):
    links = load_links(tmp_path / "no_existe.csv")
    assert links.empty
    assert list(links.columns) == LINK_COLUMNS


def test_load_links_header_only_is_empty(tmp_path):
    path = tmp_path / "links.csv"
    path.write_text(",".join(LINK_COLUMNS) + "\n", encoding="utf-8")
    links = load_links(path)
    assert links.empty
    assert list(links.columns) == LINK_COLUMNS


# --------------------------------------------------------------- apply_links


def _links(*rows):
    """Tabla de enlaces con tuplas (universidad, origen, destino, decisión)."""
    return pd.DataFrame(
        [(u, a, b, d, "") for u, a, b, d in rows], columns=LINK_COLUMNS
    )


def _succession_panel():
    return make_panel(
        _span("U", "A", 2015, 2020, 100) + _span("U", "B", 2021, 2025, 110)
    )


def test_simple_link_merges_into_one_series():
    result = apply_links(_succession_panel(), _links(("U", "A", "B", "sí")))
    assert result["series_id"].unique().tolist() == ["U|B"]
    assert result["year_start"].tolist() == list(range(2015, 2026))
    assert (result["center_code_final"] == "B").all()


def test_chain_of_three():
    panel = make_panel(
        _span("U", "A", 2015, 2018, 100)
        + _span("U", "B", 2019, 2021, 100)
        + _span("U", "C", 2022, 2025, 100)
    )
    links = _links(("U", "A", "B", "sí"), ("U", "B", "C", "sí"))
    result = apply_links(panel, links)
    assert result["series_id"].unique().tolist() == ["U|C"]
    assert len(result) == 11


def test_overlap_sums_and_weights_pct_women():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100) + _span("U", "B", 2020, 2025, 50)
    )
    panel.loc[(panel.center_code == "A") & (panel.year_start == 2020), "pct_women"] = 80.0
    panel.loc[(panel.center_code == "B") & (panel.year_start == 2020), "pct_women"] = 50.0
    result = apply_links(panel, _links(("U", "A", "B", "sí")))
    row = result[result["year_start"] == 2020].iloc[0]
    assert row["enrolled"] == 150
    assert row["pct_women"] == pytest.approx(70.0)
    assert row["n_centers"] == 2
    assert result[result["year_start"] == 2019].iloc[0]["n_centers"] == 1


def test_total_per_season_is_invariant():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100)
        + _span("U", "B", 2020, 2025, 50)
        + _span("V", "C", 2015, 2025, 70)
    )
    before = panel.groupby("year_start")["enrolled"].sum()
    result = apply_links(panel, _links(("U", "A", "B", "sí")))
    after = result.groupby("year_start")["enrolled"].sum()
    pd.testing.assert_series_equal(before, after)


@pytest.mark.parametrize("decision", ["no", "dudoso"])
def test_non_yes_decisions_ignored(decision):
    result = apply_links(_succession_panel(), _links(("U", "A", "B", decision)))
    assert sorted(result["series_id"].unique()) == ["U|A", "U|B"]


def test_empty_links_gives_own_series_per_center():
    panel = _succession_panel()
    result = apply_links(panel, pd.DataFrame(columns=LINK_COLUMNS))
    assert sorted(result["series_id"].unique()) == ["U|A", "U|B"]
    assert len(result) == len(panel)
    assert (result["n_centers"] == 1).all()


def test_unlinked_center_keeps_its_values():
    panel = make_panel(_span("U", "A", 2015, 2025, 100))
    result = apply_links(panel, pd.DataFrame(columns=LINK_COLUMNS))
    assert (result["pct_women"] == 70.0).all()
    assert result["is_provisional"].tolist() == [False] * 10 + [True]
    assert (result["center_name"] == "Centro A").all()


def test_link_to_missing_center_raises():
    with pytest.raises(ValueError, match="no existe"):
        apply_links(_succession_panel(), _links(("U", "A", "X", "sí")))


def test_link_across_universities_raises():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100) + _span("V", "B", 2021, 2025, 110)
    )
    with pytest.raises(ValueError, match="no existe"):
        apply_links(panel, _links(("U", "A", "B", "sí")))


def test_cycle_raises():
    links = _links(("U", "A", "B", "sí"), ("U", "B", "A", "sí"))
    with pytest.raises(ValueError, match="ciclo"):
        apply_links(_succession_panel(), links)


def test_two_links_from_same_center_raise():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100)
        + _span("U", "B", 2021, 2025, 60)
        + _span("U", "C", 2021, 2025, 50)
    )
    links = _links(("U", "A", "B", "sí"), ("U", "A", "C", "sí"))
    with pytest.raises(ValueError, match="más de un enlace"):
        apply_links(panel, links)


def test_all_nan_overlap_stays_nan():
    panel = make_panel(
        _span("U", "A", 2015, 2020, 100) + _span("U", "B", 2020, 2025, 50)
    )
    panel.loc[panel.year_start == 2020, "enrolled"] = np.nan
    result = apply_links(panel, _links(("U", "A", "B", "sí")))
    row = result[result["year_start"] == 2020].iloc[0]
    assert np.isnan(row["enrolled"])
    assert np.isnan(row["pct_women"])
    assert row["n_centers"] == 2


def test_overlap_provisional_and_name_from_latest_center():
    panel = make_panel(
        _span("U", "A", 2015, 2024, 100) + _span("U", "B", 2023, 2025, 50)
    )
    result = apply_links(panel, _links(("U", "A", "B", "sí")))
    assert (result["center_name"] == "Centro B").all()
    assert result.loc[result.year_start == 2025, "is_provisional"].item()
    assert not result.loc[result.year_start == 2024, "is_provisional"].item()


def test_n_source_codes():
    panel = make_panel(
        _span("U", "A", 2015, 2018, 100)
        + _span("U", "B", 2019, 2021, 100)
        + _span("U", "C", 2022, 2025, 100)
        + _span("V", "D", 2015, 2025, 100)
    )
    links = _links(("U", "A", "B", "sí"), ("U", "B", "C", "sí"))
    result = apply_links(panel, links)
    assert (result.loc[result.series_id == "U|C", "n_source_codes"] == 3).all()
    assert (result.loc[result.series_id == "V|D", "n_source_codes"] == 1).all()


def test_output_columns():
    result = apply_links(_succession_panel(), _links(("U", "A", "B", "sí")))
    assert list(result.columns) == [
        "series_id",
        "university",
        "center_code_final",
        "center_name",
        "year_start",
        "season",
        "enrolled",
        "pct_women",
        "is_provisional",
        "n_centers",
        "n_source_codes",
    ]
