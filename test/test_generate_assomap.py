"""Tests for generate_assomap.py, driven by the example MICADO workflow in
example_workflow/ (a frozen copy, so expected labels/rows don't drift with
the live pipeline repo)."""
import io
import re
import subprocess
import sys

import pytest

from conftest import EXAMPLE_MODULE, EXAMPLE_SOURCE, REPO_ROOT, SCRIPT

EXAMPLE_TASKS = [
    "micado_gen_dark",
    "micado_img_flatfield",
    "micado_spec_flatfield",
    "micado_spec_wave",
    "micado_spec_flux",
    "micado_spec_sci",
    "micado_spec_mf_model",
    "micado_spec_mf_calctrans",
    "micado_spec_mf_correct",
]


def draw_lines(tex, rowkey):
    """All \\draw [match...] lines along one row (by its rowkey)."""
    return [l for l in tex.splitlines() if r"\draw [match" in l and f"__{rowkey})" in l]


def render_wrapper(ga, *args):
    stream = io.StringIO()
    ga.render_wrapper(stream, *args)
    return stream.getvalue()


# ---------------------------------------------------------------------------
# Pure helpers (no edps needed)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, expected", [
    ("micado_spec_sci", True),
    ("metis_spec_sci", True),
    ("micado_spec_mf_correct", True),
    ("micado_spec_sci_extra", False),   # whole-name match, not prefix
    ("micado_spec_wave", False),
    ("MICADO_SPEC_SCI", False),         # case-sensitive
])
def test_science_product_glob(ga, name, expected):
    assert ga.is_science_product_task(name) is expected


@pytest.mark.parametrize("varname, expected", [
    ("raw_dark", "raw"),
    ("static_tw", "static"),
    ("persistence_map", "external"),
    ("ref_bp_map", "external"),
])
def test_classify_datasource(ga, varname, expected):
    assert ga.classify_datasource(varname) == expected


def test_parse_explicit_outputs_from_example(ga):
    outputs = ga.parse_explicit_outputs(EXAMPLE_SOURCE)
    assert outputs == {
        "mf_calctrans_task": [("MF_TELLURIC_DATA", False)],
        "mf_correct_task": [("SPEC_SCI_1D_TELL", False), ("SPEC_SCI_2D_TELL", True)],
    }


def test_parse_explicit_outputs_accumulates_lines(ga, tmp_path):
    src = tmp_path / "wkf.py"
    src.write_text(
        "# OUT: A\n"
        "# OUT: [B], C\n"
        "x = 1\n"
        "\n"
        "# OUT: D\n"
        "# unrelated comment\n"   # stops the scan: D isn't attached to y
        "y = 2\n"
    )
    assert ga.parse_explicit_outputs(src) == {"x": [("A", False), ("B", True), ("C", False)]}


def test_parse_main_input_tags_from_example(ga):
    tags = ga.parse_main_input_tags(EXAMPLE_SOURCE)
    assert tags == {
        "mf_model_task": ["final_spec_sci_1d_class"],
        "mf_calctrans_task": ["int_mf_atmoparam_class", "int_mf_bfparam_class", "int_mf_bfmodel_class"],
        "mf_correct_task": ["int_mf_calctrans_corr_class"],
    }


def test_render_wrapper_same_dir(ga, tmp_path):
    tex = render_wrapper(ga, tmp_path / "x_assomap_tikz.tex", tmp_path / "x_assomap.tex", tmp_path)
    assert r"\input@path" not in tex
    assert r"\input{x_assomap_tikz}" in tex
    assert r"\documentclass[tikz, margin=5mm, dvipsnames]{standalone}" in tex


def test_render_wrapper_sibling_dir_is_relative(ga, tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "tex").mkdir()
    tex = render_wrapper(ga, tmp_path / "out" / "x_tikz.tex", tmp_path / "out" / "x.tex", tmp_path / "tex")
    assert r"\def\input@path{{../tex/}}" in tex


def test_render_wrapper_far_dir_is_absolute(ga, tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    style = tmp_path / "styles"
    style.mkdir()
    tex = render_wrapper(ga, deep / "x_tikz.tex", deep / "x.tex", style)
    assert rf"\def\input@path{{{{{style.resolve().as_posix()}/}}}}" in tex


# ---------------------------------------------------------------------------
# Model built from the example workflow
# ---------------------------------------------------------------------------

def test_one_column_per_task_in_order(example_model):
    assert example_model["columns"] == EXAMPLE_TASKS


def test_no_inputs_column_when_first_task_has_no_raw_inputs(example_model, ga):
    assert ga.INPUTS_COLKEY not in example_model["columns"]


def test_headers(example_model):
    header = example_model["header"]
    # raw main input -> titled recipe box
    assert header["micado_gen_dark"] == r"\recipebox{\RAW{DARK}}{\REC{mcd_det_dark}}"
    # another task's product as main input -> untitled box (elbow arrow)
    assert header["micado_spec_mf_model"] == r"\recipenotitlebox{\REC{mcd_spec_mf_model}}"


@pytest.mark.parametrize("task, tags", [
    # (1) tags from downstream consumers' classification rules
    ("micado_gen_dark", ["MASTER_DARK"]),
    ("micado_spec_wave", ["MASTER_SFLAT_BLAZE", "MASTER_SFLAT_NORM", "MASTER_TW"]),
    ("micado_spec_sci", ["SPEC_SCI_1D", "SPEC_SCI_2D", "SPEC_SCI_TW"]),
    # (1) + (3) consumer tag plus an '# OUT:' comment
    ("micado_spec_mf_calctrans", ["MF_TELLURIC_CORR", "MF_TELLURIC_DATA"]),
    # (3) '# OUT:' only -- nothing consumes the final task
    ("micado_spec_mf_correct", ["SPEC_SCI_1D_TELL", "SPEC_SCI_2D_TELL"]),
])
def test_product_labels(example_model, task, tags):
    assert example_model["rows_by_key"]["D" + task]["content_tags"] == tags


def test_conditional_output_is_flagged(example_model):
    row = example_model["rows_by_key"]["Dmicado_spec_mf_correct"]
    assert row["content_lines"] == [
        (r"\PROD{SPEC_SCI_1D_TELL}", False),
        (r"\PROD{SPEC_SCI_2D_TELL}", True),
    ]
    assert re.search(r"\[scienceproduct, dashed, below=[^]]*\]\{\\PROD\{SPEC_SCI_2D_TELL\}\}", example_model["tex"])


@pytest.mark.parametrize("task, style", [
    ("micado_gen_dark", "calibproduct"),
    ("micado_spec_mf_model", "calibproduct"),
    ("micado_spec_sci", "scienceproduct"),         # consumed, but matches SCIENCE_PRODUCT_TASKS
    ("micado_spec_mf_correct", "scienceproduct"),  # leaf task
])
def test_product_styles(example_model, task, style):
    assert example_model["rows_by_key"]["D" + task]["style"] == style


@pytest.mark.parametrize("rowkey, style", [
    ("Draw_sflat_slit", "rawinput"),
    ("Dstatic_tw", "statcalfile"),
    ("Dpersistence_map", "extcalfile"),
])
def test_datasource_styles(example_model, rowkey, style):
    assert example_model["rows_by_key"][rowkey]["style"] == style


def test_input_box_sits_left_of_first_consumer(example_model):
    # raw_sflat_slit is first consumed by micado_spec_flatfield (column 3),
    # so its box goes in the preceding column.
    assert example_model["rows_by_key"]["Draw_sflat_slit"]["source_col"] == "micado_img_flatfield"


def test_optional_inputs_draw_dashed(example_model):
    lines = draw_lines(example_model["tex"], "Dpersistence_map")
    assert lines and all("dashed" in l for l in lines)


def test_required_inputs_draw_solid(example_model):
    lines = draw_lines(example_model["tex"], "Dstatic_tw")
    assert lines and not any("dashed" in l for l in lines)


def test_alternatives_only_common_tag_is_solid(example_model):
    # mf_correct's alternatives both include SPEC_SCI_1D, only one has the
    # 2D/TW products -> 1D solid, 2D and TW dashed.
    tex = example_model["tex"]
    to_correct = [l for l in tex.splitlines()
                  if r"\draw [match" in l and "RECmicado_spec_mf_correct__Dmicado_spec_sci" in l]
    by_suffix = {re.search(r"mf_correct__Dmicado_spec_sci(_\d)?\)", l).group(1): l for l in to_correct}
    assert "dashed" not in by_suffix[None]
    assert "dashed" in by_suffix["_2"]
    assert "dashed" in by_suffix["_3"]


def test_separate_assoc_calls_are_each_required(example_model):
    # micado_spec_flux pulls three distinct products out of micado_spec_wave
    # via one call each -- independent requirements, so all solid.
    tex = example_model["tex"]
    lines = [l for l in tex.splitlines()
             if r"\draw [match" in l and "-- (RECmicado_spec_flux__Dmicado_spec_wave" in l]
    assert len(lines) == 3
    assert not any("dashed" in l for l in lines)


def test_rendered_fragment_is_wellformed(example_model):
    tex = example_model["tex"]
    assert tex.count(r"\begin{tikzpicture}") == tex.count(r"\end{tikzpicture}") == 1
    # a blank line right before a matrix's closing "};" breaks pgf
    assert not re.search(r"\n\s*\n\s*\};", tex)


# ---------------------------------------------------------------------------
# Leading inputs column (fixture workflow)
# ---------------------------------------------------------------------------

def test_inputs_column_added_for_first_task_raw_inputs(inputs_first_model, ga):
    columns = inputs_first_model["columns"]
    assert columns == [ga.INPUTS_COLKEY, "fixture_flat", "fixture_wave"]
    assert inputs_first_model["header"][ga.INPUTS_COLKEY] == ""
    rows = inputs_first_model["rows_by_key"]
    assert rows["Draw_sflat_slit"]["source_col"] == ga.INPUTS_COLKEY
    assert rows["Dpersistence_map"]["source_col"] == ga.INPUTS_COLKEY
    # no trigger arrow for the inputs-only column
    assert not any(e[1] == f"REC{ga.INPUTS_COLKEY}__raw" for e in inputs_first_model["edges"])


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=REPO_ROOT)


def test_cli_writes_fragment_and_wrapper_into_dir(edps, tmp_path):
    result = run_cli(EXAMPLE_MODULE, "-i", str(REPO_ROOT), "-o", str(tmp_path))
    assert result.returncode == 0, result.stderr
    fragment = tmp_path / "micado_spec_assomap_tikz.tex"
    wrapper = tmp_path / "micado_spec_assomap.tex"
    assert fragment.exists() and wrapper.exists()
    assert "9 columns, 26 rows" in result.stdout
    wrapper_tex = wrapper.read_text()
    assert r"\input{micado_spec_assomap_tikz}" in wrapper_tex
    assert r"\input@path" in wrapper_tex  # styles live in tex/, not tmp_path


def test_cli_explicit_file_name_without_tikz_suffix(edps, tmp_path):
    result = run_cli(EXAMPLE_MODULE, "-i", str(REPO_ROOT), "-o", str(tmp_path / "diagram.tex"))
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "diagram.tex").exists()
    assert r"\input{diagram}" in (tmp_path / "diagram_standalone.tex").read_text()


def test_cli_no_wrapper(edps, tmp_path):
    result = run_cli(EXAMPLE_MODULE, "-i", str(REPO_ROOT), "-o", str(tmp_path), "--no-wrapper")
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["micado_spec_assomap_tikz.tex"]


def test_cli_unknown_package_needs_input_flag(tmp_path):
    result = run_cli("nosuchpipeline.foo_wkf", "-o", str(tmp_path))
    assert result.returncode == 2
    assert "no known workflow root" in result.stderr


# ---------------------------------------------------------------------------
# LaTeX compile
# ---------------------------------------------------------------------------

def test_wrapper_compiles(edps, pdflatex, tmp_path):
    result = run_cli(EXAMPLE_MODULE, "-i", str(REPO_ROOT), "-o", str(tmp_path))
    assert result.returncode == 0, result.stderr
    tex = subprocess.run(
        [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "micado_spec_assomap.tex"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    log = (tmp_path / "micado_spec_assomap.log").read_text(errors="replace")
    errors = [l for l in log.splitlines() if l.startswith("!")]
    assert tex.returncode == 0 and not errors, "\n".join(errors) or tex.stdout[-2000:]
    assert (tmp_path / "micado_spec_assomap.pdf").stat().st_size > 0
