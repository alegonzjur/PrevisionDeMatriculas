"""Tests de la detección de sucesiones de código de centro (fase 2)."""

import pytest

from conftest import make_panel
from prevision.linking import detect_candidates

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
