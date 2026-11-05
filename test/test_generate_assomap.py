"""Tests for generate_assomap.py, driven by the example MICADO workflow in
example_workflow/ (a frozen copy, so expected labels/rows don't drift with
the live pipeline repo)."""
import io
import re
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from conftest import EXAMPLE_MODULE, EXAMPLE_SOURCE, FIXTURES_DIR, REPO_ROOT, SCRIPT, _build

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


@pytest.mark.parametrize("tag_junction", [True, False])
def test_crossings_respect_vertical_spans_and_junctions(ga, tag_junction):
    columns = list("ABCDE")

    def node(col, row):
        return f"REC{col}__{row}"

    def row(key, col, dots=(), tags=1):
        return {"rowkey": key, "source_col": col, "dot_indices": set(dots),
                "content_lines": [("product", False)] * tags}

    rows = [row("early", "A", "DE", tags=2), row("start", "C", "B"),
            row("late", "A", "E"), row("end_C", "C"), row("end_B", "B"),
            row("end_D", "D"), row("end_E", "E")]
    extra_dots = [(node("E", "early_2"), node("A", "early_2"), node("E", "raw"))]
    if tag_junction:
        extra_dots.append((node("D", "early_2"), node("A", "early_2"), node("D", "raw")))
    edges = [
        ("arrow", node("B", "start"), node("B", "end_B"), False),
        ("arrow", node("C", "start"), node("C", "end_C"), False),
        ("arrow", node("D", "raw"), node("D", "end_D"), False),
        ("match", node("A", "early"), node("E", "early"), False),
        ("match", node("A", "early_2"), node("E", "early_2"), False),
        ("match", node("A", "late"), node("E", "late"), True),
        ("arrow", node("A", "late"), node("E", "end_E"), False),
        ("match", node("E", "late"), node("A", "late"), False),
    ]
    assert ga.edge_crossings(columns, rows, edges, node, set(), extra_dots) == [
        [], [], [], [], [] if tag_junction else ["D"],
        ["B", "C", "D"], ["B", "C", "D"], ["D", "C", "B"],
    ]
    stream = io.StringIO()
    ga._write_edges(stream, edges, columns, rows, node, set(), extra_dots)
    dashed_line = next(line for line in stream.getvalue().splitlines()
                       if r"\draw [match, dashed" in line)
    assert dashed_line.count("arc[") == 3


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


def test_only_raw_main_inputs_have_header_arrows(example_model):
    header_columns = {col for col, content in example_model["header"].items()
                      if content.startswith(r"\recipebox{")}
    arrow_columns = {a.removeprefix("REC").removesuffix("__raw")
                     for kind, a, _, _ in example_model["edges"]
                     if kind == "arrow" and a.endswith("__raw")}
    assert arrow_columns == header_columns


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
# Subworkflows with tasks absent from the module namespace
# ---------------------------------------------------------------------------

def test_internal_subworkflow_tasks_and_forward_references(ga, edps):
    model = _build(ga, "subworkflow_wkf", FIXTURES_DIR)
    assert model["columns"] == [
        "fixture_base", "fixture_prepare", "fixture_geometry", "fixture_final",
    ]
    rows = model["rows_by_key"]
    assert rows["Dfixture_geometry"]["source_col"] == "fixture_geometry"
    assert rows["Dfixture_geometry"]["content_tags"] == ["MASTER_SFLAT"]
    assert rows["Dfixture_geometry"]["style"] == "calibproduct"
    assert ("arrow", "RECfixture_base__Dfixture_base",
            "RECfixture_prepare__Dfixture_prepare", False) in model["edges"]
    assert ("arrow", "RECfixture_prepare__Dfixture_prepare",
            "RECfixture_final__Dfixture_final", False) in model["edges"]
    assert ("match", "RECfixture_geometry__Dfixture_geometry",
            "RECfixture_final__Dfixture_geometry", False) in model["edges"]
    # The associated base product is above the main-input prepare product.
    assert ("arrow", "RECfixture_final__Dfixture_base",
            "RECfixture_final__Dfixture_final", False) in model["edges"]
    assert r"\draw [arrow] (RECfixture_final__Dfixture_base) -- (RECfixture_final__Dfixture_final);" in model["tex"]
    assert not any(a == "RECfixture_final__raw" for _, a, _, _ in model["edges"])
    # A task with only its main-input dot starts there.
    assert ("arrow", "RECfixture_prepare__Dfixture_base",
            "RECfixture_prepare__Dfixture_prepare", False) in model["edges"]


@pytest.mark.parametrize("input_kind", ["main", "associated"])
def test_cyclic_task_dependencies_have_clear_error(ga, edps, input_kind):
    from edps.generator.task import TaskType

    task = SimpleNamespace(name="cyclic", type=TaskType.TASK,
                           main_input=SimpleNamespace(type=TaskType.DATA_SOURCE),
                           associated_input_groups=[])
    if input_kind == "main":
        task.main_input = task
    else:
        task.associated_input_groups = [SimpleNamespace(
            associated_inputs=[SimpleNamespace(input_task=task)])]
    with pytest.raises(ValueError, match="Cyclic task dependency.*cyclic"):
        ga.collect_tasks(SimpleNamespace(task=task))


# ---------------------------------------------------------------------------
# Bundled workflows importing multiple modules
# ---------------------------------------------------------------------------

def test_bundled_workflow_tasks_labels_and_main_input_tags(ga, edps):
    model = _build(ga, "bundled_workflow", FIXTURES_DIR)
    assert model["columns"] == ["bundled_producer", "bundled_first", "bundled_second"]
    rows = model["rows_by_key"]
    assert rows["Draw_sflat_slit"]["style"] == "rawinput"
    assert rows["Dbundled_producer"]["content_tags"] == [
        "EXTRA_PRODUCT", "MASTER_DARK", "MASTER_SFLAT",
    ]
    assert rows["Dbundled_first"]["content_tags"] == ["FIRST_ONLY"]
    assert rows["Dbundled_second"]["content_tags"] == ["SECOND_ONLY"]
    main_arrows = [e for e in model["edges"] if e[0] == "arrow"
                   and e[1].startswith("RECbundled_producer__Dbundled_producer")]
    assert main_arrows == [
        ("arrow", "RECbundled_producer__Dbundled_producer_3",
         "RECbundled_first__Dbundled_first", False),
    ]
    # Only the third stacked tag is consumed as the main input.
    assert ("arrow", "RECbundled_first__Dbundled_producer_3",
            "RECbundled_first__Dbundled_first", False) in model["edges"]


def test_module_discovery_ignores_external_imports_and_handles_cycles(ga):
    root = ModuleType("bundle.entry")
    root.__package__ = "bundle"
    child = ModuleType("bundle.child")
    external = ModuleType("other.workflow")
    root.child = child
    root.external = external
    root.alias = child
    child.root = root
    assert ga.collect_workflow_modules(root) == [root, child]


def test_empty_workflow_has_clear_error(ga, edps):
    with pytest.raises(ValueError, match="No EDPS tasks found"):
        ga.build_model(ModuleType("empty_workflow"))


def test_nonrecipe_headers(ga, edps):
    model = _build(ga, "nonrecipe_wkf", FIXTURES_DIR)
    assert "edps.executor.functions" not in model["tex"]
    association = model["header"]["fixture_association"]
    assert r"\texttt{fixture\_association}" in association
    assert "no recipe" in association
    assert r"\REC{" not in association
    wrapper = model["header"]["fixture_wrapper"]
    assert "Python task" in wrapper
    assert r"\REC{wrapped_first}" in wrapper
    assert r"\REC{wrapped_second}" in wrapper
    forward = model["header"]["fixture_forward"]
    assert r"\texttt{fixture\_forward}" in forward
    assert "Python task" in forward
    assert "no recipe" not in forward
    assert r"\REC{" not in forward


def test_legend_without_recipe_headers(ga):
    stream = io.StringIO()
    ga._write_legend(stream, {"INPUTS": "", "association": "no recipe"}, [])
    assert r"\node (leg_recipe) [recipe]{task};" in stream.getvalue()


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

@pytest.mark.parametrize("module, workflow_root, stem", [
    (EXAMPLE_MODULE, REPO_ROOT, "micado_spec"),
    ("nonrecipe_wkf", FIXTURES_DIR, "nonrecipe"),
])
def test_wrapper_compiles(edps, pdflatex, tmp_path, module, workflow_root, stem):
    result = run_cli(module, "-i", str(workflow_root), "-o", str(tmp_path))
    assert result.returncode == 0, result.stderr
    tex = subprocess.run(
        [pdflatex, "-interaction=nonstopmode", "-halt-on-error", f"{stem}_assomap.tex"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    log = (tmp_path / f"{stem}_assomap.log").read_text(errors="replace")
    errors = [l for l in log.splitlines() if l.startswith("!")]
    assert tex.returncode == 0 and not errors, "\n".join(errors) or tex.stdout[-2000:]
    assert (tmp_path / f"{stem}_assomap.pdf").stat().st_size > 0
