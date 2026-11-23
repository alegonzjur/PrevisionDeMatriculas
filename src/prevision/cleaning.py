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
