"""Control de calidad: los totales por universidad deben cuadrar entre hojas."""

import pandas as pd


def _totals(long: pd.DataFrame, name: str) -> pd.Series:
    """Suma de matriculados por (universidad, curso); todo NaN sigue siendo NaN."""
    grouped = long.groupby(["university", "year_start"])["enrolled"]
    return grouped.sum(min_count=1).rename(name)


def compare_university_totals(
    centers_long: pd.DataFrame, degrees_long: pd.DataFrame
) -> pd.DataFrame:
    """Compara los totales por universidad y curso de la hoja de centros con los de Grado.

    Devuelve las filas (university, year_start, enrolled_centers, enrolled_degrees)
    en las que difieren. Vacío si todo cuadra. NaN en ambos lados no es diferencia;
    dato en un solo lado sí lo es.
    """
    both = pd.concat(
        [_totals(centers_long, "enrolled_centers"), _totals(degrees_long, "enrolled_degrees")],
        axis=1,
    ).reset_index()
    same_value = (both["enrolled_centers"] - both["enrolled_degrees"]).abs() < 1e-9
    both_missing = both["enrolled_centers"].isna() & both["enrolled_degrees"].isna()
    return both[~(same_value | both_missing)].reset_index(drop=True)
