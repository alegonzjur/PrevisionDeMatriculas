"""Reglas de limpieza del panel de Enfermería y registro de cada paso."""

import pandas as pd

from prevision.config import LEVEL_PREFIX, NURSING_DEGREE_PATTERN


class CleaningLog:
    """Registro de cada regla aplicada: cuántas filas había antes y después."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def add(self, rule_id: str, description: str, before: int, after: int) -> None:
        self.entries.append(
            {"rule_id": rule_id, "description": description, "before": before, "after": after}
        )

    def to_markdown(self) -> str:
        lines = [
            "| Regla | Descripción | Antes | Después | Diferencia |",
            "|---|---|---:|---:|---:|",
        ]
        for e in self.entries:
            diff = e["after"] - e["before"]
            lines.append(
                f"| {e['rule_id']} | {e['description']} | {e['before']} | {e['after']} | {diff:+d} |"
            )
        return "\n".join(lines) + "\n"


def filter_nursing_degrees(wide: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """Se queda con "Graduado o Graduada en Enfermería" (formato ancho).

    Regla R1: nivel de Grado (excluye Máster y Doctorado).
    Regla R2: título que cumple NURSING_DEGREE_PATTERN. Admite el sufijo
    "por la Universidad de X" y excluye Diplomado y programas conjuntos
    (PCEO / dobles grados). Los recuentos son filas del Excel.
    """
    n_start = len(wide)
    is_grado = wide["level"].astype(str).str.startswith(LEVEL_PREFIX)
    by_level = wide[is_grado]
    log.add("R1-nivel", f"Nivel que empieza por '{LEVEL_PREFIX}'", n_start, len(by_level))

    is_nursing = by_level["degree_name"].astype(str).str.match(NURSING_DEGREE_PATTERN)
    result = by_level[is_nursing]
    log.add(
        "R2-titulacion",
        "Solo 'Graduado o Graduada en Enfermería' (excluye Diplomado, PCEO/dobles grados, "
        "másteres y doctorados)",
        len(by_level),
        len(result),
    )
    return result.reset_index(drop=True)


CENTER_KEY = ["university", "center_code"]
PANEL_COLUMNS = [
    "university",
    "center_code",
    "center_name",
    "year_start",
    "season",
    "enrolled",
    "pct_women",
    "is_provisional",
]


def unify_center_series(long: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    """Unifica las series por centro: una fila por (universidad, código de centro, curso).

    Regla R3: los códigos de titulación de un mismo centro se SUMAN por curso.
    Cubre los cambios de plan sin solape (Almería) y con solape (Granada 2025-26).
    La suma usa min_count=1: si todos los códigos son NaN, el resultado es NaN
    (nunca 0). El % de mujeres se pondera por matriculados. El nombre del centro
    es el de la fila con dato más reciente (el nombre puede cambiar con el mismo código).
    """
    df = long.copy()
    n_series = len(df.drop_duplicates(CENTER_KEY + ["degree_code"]))

    # Celdas centro-curso en las que más de un código aporta dato.
    with_data = df[df["enrolled"].notna()]
    n_overlap = int((with_data.groupby(CENTER_KEY + ["year_start"]).size() > 1).sum())

    # El % de mujeres solo pondera filas que tienen a la vez total y porcentaje.
    has_pct = df["enrolled"].notna() & df["pct_women"].notna()
    df["women"] = (df["enrolled"] * df["pct_women"]).where(has_pct)
    df["enrolled_with_pct"] = df["enrolled"].where(has_pct)

    def total(series):
        return series.sum(min_count=1)

    panel = df.groupby(CENTER_KEY + ["year_start"], as_index=False).agg(
        season=("season", "first"),
        enrolled=("enrolled", total),
        women=("women", total),
        enrolled_with_pct=("enrolled_with_pct", total),
        is_provisional=("is_provisional", "first"),
    )
    panel["pct_women"] = (panel["women"] / panel["enrolled_with_pct"]).where(
        panel["enrolled_with_pct"] > 0
    )

    # Nombre más reciente con dato; si el centro nunca tiene dato, el último nombre.
    ordered = df.sort_values("year_start")
    latest_with_data = ordered[ordered["enrolled"].notna()].groupby(CENTER_KEY)["center_name"].last()
    latest_any = ordered.groupby(CENTER_KEY)["center_name"].last()
    names = latest_with_data.combine_first(latest_any).rename("center_name").reset_index()
    panel = panel.merge(names, on=CENTER_KEY, how="left")

    panel = panel.sort_values(CENTER_KEY + ["year_start"]).reset_index(drop=True)
    n_centers = len(panel.drop_duplicates(CENTER_KEY))
    log.add(
        "R3-unificacion",
        f"Una serie por (universidad, código de centro): se suman los códigos de titulación "
        f"({n_overlap} celdas centro-curso con solape de códigos). Recuento = series",
        n_series,
        n_centers,
    )
    return panel[PANEL_COLUMNS]
