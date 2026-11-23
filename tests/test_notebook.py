import pytest

from prevision.config import PROJECT_ROOT, RAW_FILE

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

NOTEBOOK = PROJECT_ROOT / "notebooks" / "01_limpieza.ipynb"


@pytest.mark.skipif(not RAW_FILE.exists(), reason="falta el Excel real")
def test_notebook_runs_end_to_end():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    # kernel_name="python3": usa el intérprete del entorno que lanza pytest.
    client = nbclient.NotebookClient(
        notebook,
        timeout=300,
        kernel_name="python3",
        resources={"metadata": {"path": str(NOTEBOOK.parent)}},
    )
    client.execute()  # lanza CellExecutionError si alguna celda falla
    code_cells = [c for c in notebook.cells if c.cell_type == "code"]
    assert code_cells and all(c.execution_count for c in code_cells)
