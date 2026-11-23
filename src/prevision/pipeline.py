"""Pipeline ETL de la fase 1: del Excel SIIU al panel limpio por centro.

Uso para actualizar datos (sustituir data/raw/Matriculados.xlsx y ejecutar):

    python -m prevision.pipeline

Hace exactamente lo mismo que el notebook notebooks/01_limpieza.ipynb, porque
ambos llaman a las mismas funciones del paquete.
"""

import warnings
from pathlib import Path

import pandas as pd

from prevision.cleaning import CleaningLog, filter_nursing_degrees, unify_center_series
from prevision.config import PROCESSED_DIR, RAW_FILE, SHEET_CENTERS, SHEET_DEGREES
from prevision.loading import read_raw_sheet, wide_to_long
from prevision.validation import compare_university_totals


def extract(raw_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """E: lee las hojas de centros y de Grado en formato ancho (solo lectura)."""
    centers_wide = read_raw_sheet(raw_path, SHEET_CENTERS)
    degrees_wide = read_raw_sheet(raw_path, SHEET_DEGREES)
    return centers_wide, degrees_wide


def transform(
    centers_wide: pd.DataFrame, degrees_wide: pd.DataFrame
) -> tuple[pd.DataFrame, CleaningLog]:
    """T: filtra, valida totales por universidad y unifica las series por centro.

    Devuelve el panel (una fila por centro y curso) y el registro de limpieza.
    """
    log = CleaningLog()
    centers_long = wide_to_long(filter_nursing_degrees(centers_wide, log))
    # La hoja de Grado solo sirve para validar: su filtrado no entra en el registro.
    degrees_long = wide_to_long(filter_nursing_degrees(degrees_wide, CleaningLog()))

    differences = compare_university_totals(centers_long, degrees_long)
    n_compared = centers_long.groupby(["university", "year_start"]).ngroups
    log.add(
        "V1-validacion",
        f"Totales por universidad y curso frente a la hoja de Grado: "
        f"{len(differences)} diferencias en {n_compared} comparaciones",
        n_compared,
        n_compared,
    )
    if not differences.empty:
        warnings.warn(
            f"Los totales por universidad no cuadran con la hoja de Grado "
            f"({len(differences)} diferencias):\n{differences.to_string()}",
            UserWarning,
            stacklevel=2,
        )

    panel = unify_center_series(centers_long, log)
    return panel, log


def load(
    panel: pd.DataFrame, log: CleaningLog, out_dir: Path = PROCESSED_DIR
) -> tuple[Path, Path]:
    """L: escribe el panel (CSV, UTF-8) y el registro de limpieza (Markdown)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "enfermeria_panel.csv"
    log_path = out_dir / "cleaning_log.md"
    panel.to_csv(csv_path, index=False, encoding="utf-8")
    log_path.write_text(
        "# Registro de limpieza\n\n" + log.to_markdown(), encoding="utf-8"
    )
    return csv_path, log_path


def run_pipeline(raw_path: Path = RAW_FILE, out_dir: Path = PROCESSED_DIR) -> pd.DataFrame:
    """Encadena extract, transform y load. Devuelve el panel."""
    centers_wide, degrees_wide = extract(raw_path)
    panel, log = transform(centers_wide, degrees_wide)
    load(panel, log, out_dir)
    return panel


def main() -> None:
    panel = run_pipeline()
    n_centers = panel.drop_duplicates(["university", "center_code"]).shape[0]
    print(f"Panel generado: {len(panel)} filas, {n_centers} centros -> {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
