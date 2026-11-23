"""Constantes del proyecto: rutas, hojas del Excel SIIU y reglas de limpieza."""

from pathlib import Path

# Raíz del repositorio (este fichero vive en src/prevision/).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Fichero original del SIIU. NO se modifica nunca: solo se lee.
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "Matriculados.xlsx"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Hojas relevantes del Excel.
SHEET_CENTERS = "Matriculados Global por centro"  # base del panel por centro
SHEET_DEGREES = "Matriculados Grado"  # se usa para validar totales por universidad

# Estructura de cabecera (índices de fila empezando en 0).
# La fila 3 del Excel (índice 2) lleva el curso, solo sobre la columna "Total"
# de cada par (Total, % Mujeres). La cabecera real está en la fila 4 (índice 3).
SEASON_ROW = 2
HEADER_ROW = 3

# Reglas de limpieza.
LEVEL_PREFIX = "Grado"  # excluye Máster y Doctorado
# Acepta "Graduado o Graduada en Enfermería" y la variante con sufijo
# "... por la Universidad de X". Excluye Diplomado, PCEO/dobles grados, másteres
# y doctorados porque el texto debe empezar y terminar así.
NURSING_DEGREE_PATTERN = r"^Graduado o Graduada en Enfermería( por .*)?$"

# El último curso publicado (2025-26) es un avance provisional.
PROVISIONAL_YEAR = 2025

# Cabecera del Excel (en español) -> nombre de columna (en inglés).
COLUMN_MAP = {
    "Nivel": "level",
    "CCAA (univ presenciales)": "region",
    "Universidad": "university",
    "Código centro": "center_code",
    "Centro": "center_name",
    "Código Titulación": "degree_code",
    "Código de titulación": "degree_code",
    "Titulación": "degree_name",
    "Rama": "branch",
}
