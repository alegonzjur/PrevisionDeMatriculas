"""Enlace de series de centros que cambian de código (fase 2).

Un cambio administrativo de código de centro se vería en el panel como "muere una
serie y nace otra". Aquí se detectan los candidatos con una regla explícita; la
decisión de enlazarlos la toma una persona y queda en un CSV versionado.
"""

import pandas as pd

CANDIDATE_COLUMNS = [
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


def _summarize_centers(panel: pd.DataFrame) -> pd.DataFrame:
    """Una fila por centro: primer y último curso, matrícula en ambos y último nombre."""
    ordered = panel.sort_values("year_start")
    grouped = ordered.groupby(["university", "center_code"], sort=False)
    first = grouped.first()
    last = grouped.last()
    return pd.DataFrame(
        {
            "first_year": first["year_start"],
            "last_year": last["year_start"],
            "first_enrolled": first["enrolled"],
            "last_enrolled": last["enrolled"],
            "center_name": last["center_name"],
        }
    ).reset_index()


def detect_candidates(panel: pd.DataFrame) -> pd.DataFrame:
    """Detecta pares (A termina, B empieza) de la misma universidad.

    A es un centro cuyo último curso es anterior al último del panel; B es otro
    centro de la misma universidad cuyo primer curso es el último de A o el
    siguiente. No hay umbral sobre el tamaño: `size_ratio` se muestra para que
    decida una persona. `ambiguous` marca los pares en los que A tiene más de un
    B posible o B tiene más de un A posible.
    """
    centers = _summarize_centers(panel)
    final_year = panel["year_start"].max()

    ended = centers[centers["last_year"] < final_year]
    pairs = ended.merge(centers, on="university", suffixes=("_a", "_b"))
    pairs = pairs[
        (pairs["center_code_a"] != pairs["center_code_b"])
        & (pairs["first_year_b"] >= pairs["last_year_a"])
        & (pairs["first_year_b"] <= pairs["last_year_a"] + 1)
    ]
    if pairs.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)

    # Ambigüedad: cuántos B tiene cada A y cuántos A tiene cada B.
    n_successors = pairs.groupby(["university", "center_code_a"])[
        "center_code_b"
    ].transform("count")
    n_predecessors = pairs.groupby(["university", "center_code_b"])[
        "center_code_a"
    ].transform("count")

    result = pd.DataFrame(
        {
            "university": pairs["university"],
            "from_center_code": pairs["center_code_a"],
            "from_center_name": pairs["center_name_a"],
            "to_center_code": pairs["center_code_b"],
            "to_center_name": pairs["center_name_b"],
            "from_last_year": pairs["last_year_a"],
            "to_first_year": pairs["first_year_b"],
            "from_last_enrolled": pairs["last_enrolled_a"],
            "to_first_enrolled": pairs["first_enrolled_b"],
            "size_ratio": pairs["first_enrolled_b"] / pairs["last_enrolled_a"],
            "ambiguous": (n_successors > 1) | (n_predecessors > 1),
        }
    )
    return result.sort_values(["university", "from_last_year"]).reset_index(drop=True)
