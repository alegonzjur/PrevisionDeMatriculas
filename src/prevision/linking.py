"""Enlace de series de centros que cambian de código (fase 2).

Un cambio administrativo de código de centro se vería en el panel como "muere una
serie y nace otra". Aquí se detectan los candidatos con una regla explícita; la
decisión de enlazarlos la toma una persona y queda en un CSV versionado.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Contrato del fichero de enlaces confirmados (data/reference/center_links.csv).
LINK_COLUMNS = ["university", "from_center_code", "to_center_code", "decision", "note"]
# Solo esta decisión se aplica; "no" y "dudoso" se guardan para no volver a preguntar.
APPLIED_DECISION = "sí"
VALID_DECISIONS = (APPLIED_DECISION, "no", "dudoso")

SERIES_COLUMNS = [
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
    """Una fila por centro: primer y último curso, matrícula en ambos y último nombre.

    El panel es rectangular: un curso sin dato es una fila con matrícula NaN, no
    una fila ausente. Solo cuentan los cursos con matrícula informada; un centro
    sin ningún dato no aparece.
    """
    ordered = panel.dropna(subset=["enrolled"]).sort_values("year_start")
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


def load_links(path: Path) -> pd.DataFrame:
    """Lee el CSV de enlaces como texto (conserva los ceros a la izquierda).

    Si el fichero no existe devuelve una tabla vacía con las columnas del contrato.
    """
    if not Path(path).exists():
        return pd.DataFrame(columns=LINK_COLUMNS)
    links = pd.read_csv(path, dtype=str, encoding="utf-8", keep_default_na=False)
    return links[LINK_COLUMNS]


def _build_final_code_map(panel: pd.DataFrame, links: pd.DataFrame) -> dict:
    """Valida los enlaces `sí` y devuelve {(universidad, código): código final}.

    El código final es el último de la cadena A→B→C. Una persona puede confirmar
    un enlace erróneo, así que todo lo que no cuadra es un error y no se ignora.
    """
    known = set(zip(panel["university"], panel["center_code"]))
    unknown = sorted(set(links["decision"]) - set(VALID_DECISIONS))
    if unknown:
        raise ValueError(
            f"Valores de decision no válidos en los enlaces: {unknown}. "
            f"Admitidos: {list(VALID_DECISIONS)} (exactamente así, con tilde)."
        )
    applied = links[links["decision"] == APPLIED_DECISION]

    next_code: dict = {}
    for row in applied.itertuples(index=False):
        for code in (row.from_center_code, row.to_center_code):
            if (row.university, code) not in known:
                raise ValueError(
                    f"El centro {code!r} no existe en la universidad "
                    f"{row.university!r} del panel (enlace {row.from_center_code} "
                    f"→ {row.to_center_code})."
                )
        origin = (row.university, row.from_center_code)
        if origin in next_code:
            raise ValueError(
                f"Hay más de un enlace desde el centro {row.from_center_code!r} "
                f"de {row.university!r}: una serie no puede bifurcarse."
            )
        next_code[origin] = row.to_center_code

    final_code = {}
    for key in known:
        university, code = key
        seen = {code}
        while (university, code) in next_code:
            code = next_code[(university, code)]
            if code in seen:
                raise ValueError(
                    f"Los enlaces de {university!r} forman un ciclo que pasa "
                    f"por el centro {code!r}."
                )
            seen.add(code)
        final_code[key] = code
    return final_code


def apply_links(panel: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    """Une en una serie los centros enlazados y devuelve el panel por `series_id`.

    `series_id = "{universidad}|{código final}"`. Si dos centros de una serie
    coinciden en un curso se suma la matrícula (`min_count=1`: NaN si todos son
    NaN), `pct_women` se pondera por matrícula, `is_provisional` es verdadero si
    alguno lo es y el nombre es el del centro más reciente de la serie.
    """
    final_code = _build_final_code_map(panel, links)
    data = panel.copy()
    keys = list(zip(data["university"], data["center_code"]))
    data["center_code_final"] = [final_code[k] for k in keys]
    data["series_id"] = data["university"] + "|" + data["center_code_final"]
    data["n_source_codes"] = data.groupby("series_id")["center_code"].transform("nunique")

    # Nombre: el del centro con el curso más reciente (a igualdad, el del código final).
    data["_is_final"] = data["center_code"] == data["center_code_final"]
    names = (
        data.sort_values(["year_start", "_is_final"])
        .groupby("series_id")["center_name"]
        .last()
    )

    # Media ponderada de % mujeres: solo cuentan filas con matrícula y porcentaje.
    has_both = data["enrolled"].notna() & data["pct_women"].notna()
    data["_weight"] = data["enrolled"].where(has_both)
    data["_weighted_pct"] = data["pct_women"] * data["_weight"]

    grouped = data.groupby(["series_id", "year_start"], sort=True)
    out = grouped.agg(
        university=("university", "first"),
        center_code_final=("center_code_final", "first"),
        season=("season", "first"),
        enrolled=("enrolled", lambda s: s.sum(min_count=1)),
        n_centers=("center_code", "size"),
        n_source_codes=("n_source_codes", "first"),
        is_provisional=("is_provisional", "any"),
        _weight=("_weight", lambda s: s.sum(min_count=1)),
        _weighted_pct=("_weighted_pct", lambda s: s.sum(min_count=1)),
        _first_pct=("pct_women", "first"),
    ).reset_index()

    weighted = out["_weighted_pct"] / out["_weight"]
    weighted = weighted.where(out["_weight"] > 0, np.nan)
    # Con un solo centro el porcentaje es el original (sin ruido de coma flotante).
    out["pct_women"] = np.where(out["n_centers"] == 1, out["_first_pct"], weighted)
    out["center_name"] = out["series_id"].map(names)
    return out[SERIES_COLUMNS]
