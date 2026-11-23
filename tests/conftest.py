"""Ayudas para los tests: construye un Excel pequeño con la estructura del SIIU."""

from pathlib import Path

from openpyxl import Workbook

from prevision.config import SHEET_CENTERS, SHEET_DEGREES

# (clave en inglés, cabecera en español) de las columnas fijas de cada hoja.
CENTER_HEADERS = [
    ("level", "Nivel"),
    ("region", "CCAA (univ presenciales)"),
    ("university", "Universidad"),
    ("center_code", "Código centro"),
    ("center_name", "Centro"),
    ("degree_code", "Código Titulación"),
    ("degree_name", "Titulación"),
    ("branch", "Rama"),
]
DEGREE_HEADERS = [
    ("level", "Nivel"),
    ("region", "CCAA (univ presenciales)"),
    ("university", "Universidad"),
    ("degree_code", "Código de titulación"),
    ("degree_name", "Titulación"),
    ("branch", "Rama"),
]

NURSING_TITLE = "Graduado o Graduada en Enfermería"


def make_row(
    university="Granada",
    center_code="18009225",
    center_name="Facultad de Ciencias de la Salud",
    degree_code="2501351",
    degree_name=NURSING_TITLE,
    values=None,
    **extra,
):
    """Fila de prueba con valores por defecto razonables.

    `values` es {año_inicio: (total, pct_mujeres)}; None deja la celda vacía.
    """
    row = {
        "level": "Grado y 1º y 2º ciclo",
        "region": "Andalucía",
        "university": university,
        "center_code": center_code,
        "center_name": center_name,
        "degree_code": degree_code,
        "degree_name": degree_name,
        "branch": "Ciencias de la Salud",
        "values": values or {},
    }
    row.update(extra)
    return row


def _write_sheet(ws, headers, rows, years, trailing_empty_rows):
    # Tres filas de título; los cursos van en la fila 3 y la cabecera en la 4.
    ws.cell(row=1, column=1, value="Serie de estudiantes matriculados (prueba)")
    ws.cell(row=2, column=1, value="2025-2026: Datos provisionales Avance")
    n_fixed = len(headers)
    for i, (_, spanish) in enumerate(headers, start=1):
        ws.cell(row=4, column=i, value=spanish)
    for k, year in enumerate(years):
        col = n_fixed + 1 + 2 * k
        ws.cell(row=3, column=col, value=f"{year}-{year + 1}")  # solo sobre "Total"
        ws.cell(row=4, column=col, value="Total")
        ws.cell(row=4, column=col + 1, value="% Mujeres")
    for r, row in enumerate(rows, start=5):
        for i, (key, _) in enumerate(headers, start=1):
            ws.cell(row=r, column=i, value=row[key])
        for k, year in enumerate(years):
            total, pct = row["values"].get(year, (None, None))
            col = n_fixed + 1 + 2 * k
            ws.cell(row=r, column=col, value=total)
            ws.cell(row=r, column=col + 1, value=pct)
    # Filas finales totalmente vacías (celdas con formato pero sin valor).
    for r in range(5 + len(rows), 5 + len(rows) + trailing_empty_rows):
        ws.cell(row=r, column=1, value=None)


def build_workbook(
    path: Path,
    centers_rows: list[dict],
    degrees_rows: list[dict],
    years: tuple[int, ...] = (2025, 2024, 2023),
    trailing_empty_rows: int = 0,
) -> Path:
    """Escribe un Excel con las hojas de centros y de Grado imitando el real."""
    wb = Workbook()
    ws_centers = wb.active
    ws_centers.title = SHEET_CENTERS
    _write_sheet(ws_centers, CENTER_HEADERS, centers_rows, years, trailing_empty_rows)
    ws_degrees = wb.create_sheet(SHEET_DEGREES)
    _write_sheet(ws_degrees, DEGREE_HEADERS, degrees_rows, years, trailing_empty_rows)
    wb.save(path)
    return path
