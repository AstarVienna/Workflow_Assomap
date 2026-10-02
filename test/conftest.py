"""Shared fixtures. Run with the edps-engine Python, e.g.

    /Users/janus/miniconda3/envs/pyreduce_edps/bin/python3.12 -m pytest test

Tests that need the real `edps` engine are skipped if it isn't importable.
"""
import importlib.util
import io
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "generate_assomap.py"
EXAMPLE_MODULE = "example_workflow.micado_spec_wkf"
EXAMPLE_SOURCE = REPO_ROOT / "example_workflow" / "micado_spec_wkf.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# example_workflow is imported as a package from the repo root (its modules
# use relative imports); the fixture workflows import from it too.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def ga():
    """The generate_assomap script, imported as a module."""
    spec = importlib.util.spec_from_file_location("generate_assomap", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def edps():
    return pytest.importorskip("edps")


def _build(ga, module_name, workflow_root):
    wkf = ga.load_workflow(module_name, workflow_root)
    columns, header, rows, edges, node, elbow_dots, extra_dots = ga.build_model(wkf)
    stream = io.StringIO()
    ga.render(stream, columns, header, rows, edges, node, elbow_dots, extra_dots)
    return {
        "columns": columns,
        "header": header,
        "rows": rows,
        "rows_by_key": {r["rowkey"]: r for r in rows},
        "edges": edges,
        "tex": stream.getvalue(),
    }


@pytest.fixture(scope="session")
def example_model(ga, edps):
    """build_model() + render() output for the example MICADO workflow."""
    return _build(ga, EXAMPLE_MODULE, REPO_ROOT)


@pytest.fixture(scope="session")
def inputs_first_model(ga, edps):
    """Model for a workflow whose first task has raw associated inputs."""
    return _build(ga, "inputs_first_wkf", FIXTURES_DIR)


@pytest.fixture(scope="session")
def pdflatex():
    exe = shutil.which("pdflatex")
    if exe is None:
        pytest.skip("pdflatex not installed")
    return exe
