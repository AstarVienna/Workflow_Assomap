#!/usr/bin/env python3
"""Generate a tikz "assomap" fragment (see example_assomap_tikz.tex) from a
built EDPS workflow module, by introspecting the actual Task/DataSource
objects the module builds -- not by parsing the Python source.

Must be run with an interpreter that has the real `edps` engine installed
Usage:
    .../miniconda3/envs/edps_env/bin/python3.12 \\
        generate_assomap.py micado.micado_spec_wkf
    .../miniconda3/envs/edps_env/bin/python3.12 \\
        generate_assomap.py metis.metis_ifu_wkf -i ~/Code/pipelines/metispipeline/metisp/workflows/

Layout rules (mirroring the hand-drawn example):
  - one column per task, in the order tasks appear in the workflow module,
    plus a leading inputs-only column if the first task has raw/reference
    associated inputs (so its own trigger arrow doesn't cross their boxes)
  - row 1: each column's trigger -- \\recipebox{RAW}{recipe} if the task's
    main input is raw data, \\recipenotitlebox{recipe} if its main input is
    another task's product (drawn as an elbow arrow instead)
  - one row per distinct raw/reference/static input or task output, created
    the first time it is encountered scanning columns left to right; reused
    (as a small connection dot + match line) every later time it is consumed
  - solid match/arrow = required input, dashed = optional (min_ret=0)

Classifying a DataSource as raw/static/external input is done from the
Python variable name it is bound to in the workflow module (raw_* / static_*
/ everything else), since the edps object model does not otherwise
distinguish them. A task's product is drawn as a scienceproduct if nothing
else consumes it, or if its task name matches one of the shell-style
wildcard patterns in SCIENCE_PRODUCT_TASKS below -- otherwise it is drawn as an (intermediate) calibproduct.

A task's own recipe/workflow definition never states its output's pro.catg
directly -- the workflow instead tags it where it is *consumed*, e.g.
`.with_associated_input(dark_task, [master_dark_class])` or
`.with_main_input(mf_model_task, [int_mf_model_class])`. edps records that
classification on the referenced task itself (`task.classification_rules`),
so a task's product box is labelled with that tag (e.g. MASTER_DARK) once
any consumer supplies one. For a task with nothing downstream (e.g.
a pipeline's final, unconsumed task), the workflow author can instead write
a `# OUT: TAG` comment directly above that task's assignment; those comments
are read straight from the source (edps has no runtime concept of them) and
used as a fallback label (or added to the inferred tags, for a recipe with
more outputs than any single consumer infers). Failing both, the label falls
back to the task's own Python name. A tag written as `# OUT: [TAG]` is drawn
as a conditional product with a dashed border.

`.with_alternatives(alternative_associated_inputs()...)` lists more than one
way to satisfy *one* logical input slot (e.g. "sci output tagged [1D, 2D]"
or, failing that, "sci output tagged [1D]") -- edps groups these together
(task.associated_input_groups), so only tags common to every alternative
(with min_ret >= 1) draw solid; a tag only sometimes part of the alternative
chosen (e.g. the 2D half) draws dashed. This is different from several
*separate* `.with_associated_input(x, [tag])` calls naming the same x with
different tags (e.g. mcd_spec_flux pulling three distinct products out of
mcd_spec_wave) -- each such call is its own group of one, so each is an
independent, separately-required connection, not an alternative of the
others; all draw solid unless *that* one call passed min_ret=0.
"""
import argparse
import ast
import fnmatch
import importlib
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

OUT_COMMENT_RE = re.compile(r"^\s*#\s*OUT:\s*(.+?)\s*$")

# This tool lives standalone (not nested inside any one pipeline's repo), so
# there is no single relative path to "the" workflow directory -- instead,
# map each known workflow module's top-level package to where its pipeline
# checkout keeps workflow definitions, relative to the shared pipelines root
# (sibling checkouts of micado-pipe/metispipeline/... on this machine). Pass
# -i/--input explicitly for anything not listed here.
PIPELINES_ROOT = Path("~/Code/pipelines").expanduser()
KNOWN_WORKFLOW_ROOTS = {
    "micado": PIPELINES_ROOT / "micado-pipe" / "edps" / "workflow",
    "metis": PIPELINES_ROOT / "metispipeline" / "metisp" / "workflows",
}

# Shell-style wildcard patterns (fnmatch: *, ?, [seq]; matched against the
# whole task name, case-sensitively) for tasks whose product is drawn as a
# scienceproduct even though something downstream consumes it.
SCIENCE_PRODUCT_TASKS = [
    "*_spec_sci",
    "*_spec_mf_correct",
]


def is_science_product_task(name):
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in SCIENCE_PRODUCT_TASKS)


# colkey of the leading inputs-only column inserted when the first task has
# raw/reference inputs of its own (see build_model). Not a valid task slug.
INPUTS_COLKEY = "INPUTS"


def load_workflow(module_name, workflow_root):
    sys.path.insert(0, str(workflow_root))
    from edps.generator.task import TaskType  # noqa: F401  (fail fast if edps is missing)
    return importlib.import_module(module_name)


def slug(name):
    return "".join(ch if ch.isalnum() else "_" for ch in name)


def tex_escape(text):
    return text.replace("_", r"\_")


def parse_explicit_outputs(source_path):
    """Map task variable name -> [(tag, conditional), ...] from '# OUT: TAG'
    comment line(s) directly above that task's top-level assignment
    (consecutive '# OUT:' lines accumulate; a blank line or any other
    comment stops the scan). A tag written as '[TAG]' is only conditionally
    produced (e.g. a telluric-corrected 2D spectrum that only exists when
    the 2D input was itself available) and is flagged accordingly."""
    lines = Path(source_path).read_text().splitlines()
    tree = ast.parse("\n".join(lines), filename=str(source_path))
    outputs = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        tags = []
        lineno = node.lineno - 1  # 1-indexed; the line directly above
        while lineno >= 1:
            m = OUT_COMMENT_RE.match(lines[lineno - 1])
            if not m:
                break
            new_tags = []
            for t in m.group(1).split(","):
                t = t.strip()
                if not t:
                    continue
                conditional = t.startswith("[") and t.endswith("]")
                new_tags.append((t.strip("[]").strip(), conditional))
            tags = new_tags + tags
            lineno -= 1
        if tags:
            outputs[target.id] = tags
    return outputs


def parse_main_input_tags(source_path):
    """Map task variable name -> [tag variable names] literally passed as
    the second argument to that task's own `.with_main_input(x, [tags])`
    call, e.g. mf_calctrans_task -> ["int_mf_atmoparam_class", ...].

    edps merges every tag from `.with_main_input`/`.with_associated_input`
    onto the *referenced* task's shared classification_rules with no
    per-call record of which tags came from which caller. That's fine when
    a task consumes another's entire output, but a main input can name only
    *some* of an upstream row's several output tags (e.g. mf_model consumes
    just spectro_science_calibration_task's SPEC_SCI_1D, not its 2D/
    TRACE_WAVE outputs too) -- indistinguishable at runtime from consuming
    all of them, so read the literal tag list back out of the source."""
    lines = Path(source_path).read_text().splitlines()
    tree = ast.parse("\n".join(lines), filename=str(source_path))
    result = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        for call in ast.walk(node.value):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "with_main_input" and len(call.args) > 1
                    and isinstance(call.args[1], ast.List)):
                result[target.id] = [elt.id for elt in call.args[1].elts if isinstance(elt, ast.Name)]
                break
    return result


def product_output_tags(task, explicit_outputs):
    """A task's output tag(s), each paired with whether it is only
    conditionally produced: tags inferred from a downstream consumer's
    classification (`.with_associated_input(x, [tag_class])`) are always
    unconditional; likewise a `.with_output_filter(tag_class, ...)` call is
    the task's own unambiguous declaration of what it produces (used by
    e.g. METIS-style workflows, which otherwise never tag `.with_associated
    _input()`/`.with_main_input()` calls at all -- see the module docstring).
    A '# OUT: [TAG]' comment can mark a tag -- inferred or not -- as
    conditional (e.g. mcd_spec_mf_correct's SPEC_SCI_2D_TELLURIC only exists
    when its 2D input was itself available). Returns None if no tag is known
    at all, so the caller can fall back to the task's own name."""
    inferred = {cr.classification for cr in task.classification_rules if cr.classification}
    if getattr(task, "output_filter_mode", None) == "SELECT":
        inferred |= set(task.output_filter)
    explicit = dict(explicit_outputs.get(id(task), []))  # tag -> conditional
    tags = sorted(inferred | set(explicit))
    if not tags:
        return None
    return [(tag, explicit.get(tag, False)) for tag in tags]


def classify_datasource(varname):
    if varname.startswith("raw_"):
        return "raw"
    if varname.startswith("static_"):
        return "static"
    return "external"


DS_STYLE = {
    "raw": ("rawinput", r"\RAW{%s}"),
    "static": ("statcalfile", r"\STATCALIB{%s}"),
    "external": ("extcalfile", r"\EXTCALIB{%s}"),
}


def build_model(wkf):
    from edps.generator.task import TaskType

    tasks = [v for v in vars(wkf).values() if getattr(v, "type", None) == TaskType.TASK]
    datasource_varname = {
        id(v): n for n, v in vars(wkf).items() if getattr(v, "type", None) == TaskType.DATA_SOURCE
    }
    explicit_outputs_by_varname = parse_explicit_outputs(wkf.__file__)
    explicit_outputs = {
        id(v): explicit_outputs_by_varname[n]
        for n, v in vars(wkf).items()
        if n in explicit_outputs_by_varname
    }
    main_input_tag_varnames = parse_main_input_tags(wkf.__file__)
    main_input_tags = {
        id(v): [
            getattr(wkf, tv).classification for tv in main_input_tag_varnames[n]
            if hasattr(wkf, tv)
        ]
        for n, v in vars(wkf).items()
        if n in main_input_tag_varnames
    }

    columns = []          # ordered list of colkeys
    colkey_of_task = {}   # id(task) -> colkey
    header = {}           # colkey -> tex content for row 1
    rows = []             # ordered list of row dicts
    row_by_id = {}        # id(object) -> row dict
    edges = []            # ('arrow'|'match', from_node, to_node, dashed)
    main_input_consumers = set()  # id(task) for tasks consumed as another task's main input
    elbow_dots = set()    # (colkey, rowkey) cells a main-input elbow arrow bends through
    main_input_links = []  # (colkey, own_row, main_input_task_row); arrows drawn once every
                            # row's output tags are known (a main input can carry >1 tag too,
                            # e.g. mf_calctrans consuming three of mf_model's outputs)

    def rowkey_for(obj, is_task):
        if is_task:
            return "D" + slug(colkey_of_task[id(obj)])
        return "D" + slug(datasource_varname.get(id(obj), obj.name).lower())

    def node(colkey, rowkey):
        # "__" (not "_", which colkey/rowkey may themselves contain) separates
        # the column from the row so node_col() can split unambiguously.
        return f"REC{colkey}__{rowkey}"

    def get_or_create_row(obj, is_task, source_col):
        """Return (row, created). A newly-created row's source is source_col;
        an existing row is untouched -- the caller must treat source_col as a
        consumer instead."""
        row = row_by_id.get(id(obj))
        if row is not None:
            return row, False
        row = {
            "rowkey": rowkey_for(obj, is_task),
            "source_col": source_col,
            "is_task": is_task,
            "obj": obj,
            "consumers": [],  # list of (colkey, entries), in column order;
                               # entries = [(frozenset(tags), min_ret), ...]
        }
        rows.append(row)
        row_by_id[id(obj)] = row
        return row, True

    for task in tasks:
        colkey = slug(task.name)
        columns.append(colkey)
        colkey_of_task[id(task)] = colkey

        main_input = task.main_input
        main_input_task_row = None
        if main_input.type == TaskType.DATA_SOURCE:
            header[colkey] = (
                r"\recipebox{" + (DS_STYLE["raw"][1] % main_input.name) + "}{" +
                r"\REC{" + task.command + "}}"
            )
        else:
            header[colkey] = r"\recipenotitlebox{\REC{" + task.command + "}}"
            main_input_task_row = row_by_id[id(main_input)]
            main_input_consumers.add(id(main_input))

        prev_colkey = columns[-2] if len(columns) >= 2 else None

        # A single `.with_associated_input(x, [tag])` call is its own group of
        # one -- an independent, separately-required input. `.with_alternatives
        # (alternative_associated_inputs()...)` instead puts *several*
        # AssociatedInputs for the same logical input slot into one group --
        # e.g. "sci output tagged [1D, 2D]" or, failing that, "sci output
        # tagged [1D]" -- only one of which will actually be picked. Iterate
        # associated_input_groups() (not the flattened list) so that
        # distinction survives: three separate calls naming three different
        # tags of the same upstream task (e.g. mcd_spec_flux pulling
        # MASTER_TW/_NORM/_BLAZE from mcd_spec_wave) are three independent
        # requirements, not alternatives of each other, even though
        # flatten_associated_inputs() lists them identically. Each item's
        # "groups" is a list of that item's per-group entry lists; a tag is
        # required only if *some* group requires it in every one of that
        # group's own alternatives (see edge-expansion below).
        assoc_by_item = {}
        assoc_order = []
        for group in task.associated_input_groups:
            entries_by_item_in_group = {}
            for assoc in group.associated_inputs:
                key = id(assoc.input_task)
                if key not in assoc_by_item:
                    assoc_by_item[key] = {
                        "item": assoc.input_task,
                        "is_task": assoc.input_type == TaskType.TASK,
                        "groups": [],
                    }
                    assoc_order.append(key)
                tags = frozenset(cr.classification for cr in assoc.classification_rules if cr.classification)
                entries_by_item_in_group.setdefault(key, []).append((tags, assoc.min_ret))
            for key, entries in entries_by_item_in_group.items():
                assoc_by_item[key]["groups"].append(entries)

        for key in assoc_order:
            info = assoc_by_item[key]
            item = info["item"]
            is_item_task = info["is_task"]
            groups = info["groups"]
            if is_item_task:
                # a task's product always lives in its own column; nothing to shift.
                row, created = get_or_create_row(item, True, colkey)
                if not created:
                    row["consumers"].append((colkey, groups))
            elif id(item) in row_by_id:
                row_by_id[id(item)]["consumers"].append((colkey, groups))
            else:
                # Place a raw/reference input one column to the *left* of its
                # first consumer (the preceding column's own trigger arrow has
                # already ended above this row, since every column's own
                # product row is created before any later column's rows), so
                # this column's own header->product arrow doesn't run through
                # the box. The first task has no earlier column, so give it a
                # leading inputs-only column (no recipe, no arrow) instead.
                if prev_colkey is None:
                    if INPUTS_COLKEY not in header:
                        columns.insert(0, INPUTS_COLKEY)
                        header[INPUTS_COLKEY] = ""
                    box_col = INPUTS_COLKEY
                else:
                    box_col = prev_colkey
                row, _ = get_or_create_row(item, False, box_col)
                if box_col != colkey:
                    row["consumers"].append((colkey, groups))

        own_row, _ = get_or_create_row(task, True, colkey)
        edges.append(("arrow", node(colkey, "raw"), node(colkey, own_row["rowkey"]), False))
        if main_input_task_row is not None:
            main_input_links.append((colkey, own_row, main_input_task_row, id(task)))

    # decide calibproduct vs scienceproduct for task-output rows, and content:
    # content_lines is [(tex_snippet, conditional), ...]; content_tags is the
    # parallel list of raw tag strings (None if falling back to the task's
    # own name, since there is then nothing for a consumer to match against).
    consumed_task_ids = {id(r["obj"]) for r in rows if r["is_task"] and r["consumers"]}
    consumed_task_ids |= main_input_consumers
    for row in rows:
        if not row["is_task"]:
            continue
        task = row["obj"]
        is_leaf = id(task) not in consumed_task_ids
        row["style"] = "scienceproduct" if (is_leaf or is_science_product_task(task.name)) else "calibproduct"
        tag_pairs = product_output_tags(task, explicit_outputs)
        if tag_pairs is None:
            row["content_tags"] = None
            row["content_lines"] = [(r"\texttt{%s}" % tex_escape(task.name), False)]
        else:
            row["content_tags"] = [tag for tag, _ in tag_pairs]
            row["content_lines"] = [(r"\PROD{%s}" % tag, conditional) for tag, conditional in tag_pairs]

    for row in rows:
        if row["is_task"]:
            continue
        ds = row["obj"]
        kind = classify_datasource(datasource_varname.get(id(ds), ""))
        style, macro = DS_STYLE[kind]
        row["style"] = style
        row["content_tags"] = None
        row["content_lines"] = [(macro % ds.name, False)]

    # Expand each row's consumer list into chained match edges. A consumer
    # is "generic" (no classification tags given at all -- e.g. a plain raw
    # or reference input) and simply connects to the row's primary box. A
    # consumer that *did* supply tags (an ordinary `[tag_class]` input, or
    # several alternatives with different tag sets) connects to each
    # specific tagged box it names, required (solid) only if that tag is
    # present with min_ret>=1 in *every* alternative -- this is what makes an
    # alternative-only tag (e.g. mf_correct's optional SPEC_SCI_2D) dashed
    # while a tag common to all alternatives (SPEC_SCI_1D) stays solid.
    def stack_node(colkey, rowkey, idx):
        # idx 0 is the row's own primary node; idx > 0 is one of the extra
        # boxes stacked below it on the *source* side (see render()).
        base = node(colkey, rowkey)
        return base if idx == 0 else f"{base}_{idx + 1}"

    extra_dots = []  # (dest_id, src_tag_node, x_ref_node) for idx>0 connection dots,
                      # positioned outside the matrix -- see render()

    # A main input can carry more than one tag too (e.g. mf_calctrans's main
    # input lists three of mf_model's outputs), so draw one arrow per output
    # tag *this call* named -- not necessarily every tag the source row ends
    # up with, since other, unrelated callers can tag that same row with
    # more (e.g. mf_model's main input names only spectro_science_calibration
    # _task's SPEC_SCI_1D, even though that row also carries SPEC_SCI_2D and
    # SPEC_SCI_TRACE_WAVE for other consumers). Each arrow ends on the
    # consumer's own product, since that product isn't itself split by which
    # input tag fed it.
    for colkey, own_row, main_input_task_row, consumer_task_id in main_input_links:
        all_tags = main_input_task_row.get("content_tags")
        wanted = main_input_tags.get(consumer_task_id)
        if all_tags and wanted:
            indices = [all_tags.index(t) for t in wanted if t in all_tags]
        else:
            indices = [0]
        dest_node = stack_node(colkey, own_row["rowkey"], 0)
        for idx in indices:
            src_node = stack_node(main_input_task_row["source_col"], main_input_task_row["rowkey"], idx)
            edges.append(("arrow", src_node, dest_node, False))
            if idx == 0:
                # Point straight at this column's own product, not at its
                # header: the header sits *above* rows this column shares
                # with earlier columns' rows, so an arrow ending there would
                # run back up through, and overlap in the opposite direction
                # from, the header->product arrow above -- looking like a
                # double-headed arrow. Ending both arrows at the same
                # (downstream) product keeps every arrow pointing the same
                # way: down, into a product. The "-|" elbow bends through
                # this column at the source's row height before heading
                # down; mark that bend with a connection dot too, same as
                # any other consumed row.
                elbow_dots.add((colkey, main_input_task_row["rowkey"]))
            else:
                extra_dots.append((
                    stack_node(colkey, main_input_task_row["rowkey"], idx), src_node, node(colkey, "raw"),
                ))

    for row in rows:
        tag_index = {t: i for i, t in enumerate(row["content_tags"])} if row["content_tags"] else {}
        dot_indices = set()  # colkeys needing an *idx-0* connection dot (placed in the matrix cell)

        generic = []
        per_tag = {}
        for colkey, groups in row["consumers"]:
            flat_entries = [entry for group_entries in groups for entry in group_entries]
            all_tags = frozenset().union(*(tags for tags, _ in flat_entries)) if flat_entries else frozenset()
            if not all_tags or not tag_index:
                dashed = not any(min_ret >= 1 for _, min_ret in flat_entries)
                generic.append((colkey, dashed))
                dot_indices.add(colkey)
                continue
            # A tag is required if *any* group guarantees it -- each group is
            # itself mandatory (all of a consumer's separate `.with_associated
            # _input(...)` calls must be satisfied), and within one group only
            # the tags common to every alternative (with min_ret>=1) are
            # guaranteed, since only one alternative is actually picked.
            required = frozenset()
            for group_entries in groups:
                group_required = None
                for tags, min_ret in group_entries:
                    candidate = tags if min_ret >= 1 else frozenset()
                    group_required = candidate if group_required is None else (group_required & candidate)
                required |= (group_required or frozenset())
            for tag in all_tags:
                if tag in tag_index:
                    per_tag.setdefault(tag, []).append((colkey, tag not in required))

        row["dot_indices"] = dot_indices

        prev_node = stack_node(row["source_col"], row["rowkey"], 0)
        for colkey, dashed in generic:
            this_node = stack_node(colkey, row["rowkey"], 0)
            edges.append(("match", prev_node, this_node, dashed))
            prev_node = this_node

        for tag, consumers_for_tag in per_tag.items():
            idx = tag_index[tag]
            src_tag_node = stack_node(row["source_col"], row["rowkey"], idx)
            prev_node = src_tag_node
            for colkey, dashed in consumers_for_tag:
                this_node = stack_node(colkey, row["rowkey"], idx)
                edges.append(("match", prev_node, this_node, dashed))
                prev_node = this_node
                if idx == 0:
                    dot_indices.add(colkey)
                else:
                    # A dot for a non-primary tag can't just be "0.35cm below
                    # the primary dot": the source side's boxes are much
                    # taller than these tiny dots, so a fixed gap wouldn't
                    # land at the same height as the source box it connects
                    # to, and the line would be diagonal instead of
                    # horizontal. Read the *actual* height straight off the
                    # source tag node instead, combined with this column's
                    # own x position (via the `calc` library's "-|").
                    extra_dots.append((this_node, src_tag_node, node(colkey, "raw")))

    return columns, header, rows, edges, node, elbow_dots, extra_dots


def _writelines(stream, *lines):
    """Write each line followed by a newline."""
    for line in lines:
        stream.write(line + "\n")


@contextmanager
def _tex_group(stream, begin, end):
    """Write `begin`, the body, then `end` -- so every opened TikZ group
    (tikzpicture, matrix) is closed in exactly one place."""
    _writelines(stream, *begin)
    yield
    _writelines(stream, *end)


def _product_cell(row, node_id):
    """The matrix cell holding a row's own box(es): one node per output, the
    extra ones stacked below the first."""
    def style_for(conditional):
        # a conditionally-produced output (from an '# OUT: [TAG]' comment)
        # gets a dashed border, same visual language as an optional input
        # connection.
        return f"{row['style']}, dashed" if conditional else row["style"]

    first_tex, first_cond = row["content_lines"][0]
    stmts = [rf"\node ({node_id})[{style_for(first_cond)}]{{{first_tex}}};"]
    prev_id = node_id
    for i, (extra, conditional) in enumerate(row["content_lines"][1:], start=2):
        # a recipe with more than one output: stack the extra product(s)
        # tighter than the row-to-row spacing, so they read as one recipe's
        # outputs rather than separate rows. "of <prev_id>" is explicit --
        # relying on positioning's "most recently defined node" default is
        # unreliable inside a matrix cell (it does not chain as expected).
        this_id = f"{node_id}_{i}"
        opts = f"{style_for(conditional)}, below=0.175cm of {prev_id}"
        stmts.append(rf"\node ({this_id})[{opts}]{{{extra}}};")
        prev_id = this_id
    return " ".join(stmts)


def _matrix_cell(row, col, node, elbow_dots):
    node_id = node(col, row["rowkey"])
    if col == row["source_col"]:
        return _product_cell(row, node_id)
    if col in row["dot_indices"] or (col, row["rowkey"]) in elbow_dots:
        return rf"\node ({node_id})[connection]{{}};"
    return rf"\node ({node_id})[empty]{{}};"


def _write_matrix_row(stream, cells):
    _writelines(stream, "    " + " &\n    ".join(cells) + r" \\")


def _write_preamble(stream):
    _writelines(
        stream,
        r"%%%%%%%%%%%%%%%%%% BEGIN DOCUMENT %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%",
        r"% Auto-generated by generate_assomap.py -- do not hand-edit, regenerate instead.",
        r"\sffamily",
        "",
        r"\input{black_style}",
        r"\input{recipe_config}",
        "",
    )


def _write_recipe_matrix(stream, columns, header, rows, node, elbow_dots):
    begin = [r"  \matrix (recipes) [column sep=1mm, row sep=0.5cm]{", ""]
    end = [r"  };    % end matrix (recipes)", ""]
    with _tex_group(stream, begin, end):
        _writelines(stream, "    % Row raw : trigger (raw main input, or hand-off from a previous task)")
        _write_matrix_row(stream, [rf"\node[above] ({node(c, 'raw')}){{{header[c]}}};" for c in columns])
        for row in rows:
            # the blank separator goes *before* each row, never after the
            # last: a blank line right before the closing "};" corrupts pgf's
            # matrix nesting state (manifests later as a spurious "cannot
            # nest pgfmatrix environments" error at the *next* \matrix, e.g.
            # the legend)
            _writelines(stream, "", f"    % Row {row['rowkey']} : {row['obj'].name}")
            _write_matrix_row(stream, [_matrix_cell(row, c, node, elbow_dots) for c in columns])


def _write_extra_dots(stream, extra_dots):
    if not extra_dots:
        return
    _writelines(
        stream,
        "  %% Connection dots for non-primary output tags: positioned by",
        "  %% reading the source tag's actual height (-| from the calc library),",
        "  %% not by a fixed offset, so the dashed/solid line to them is level.",
    )
    for dest_id, src_tag_node, x_ref_node in extra_dots:
        _writelines(stream, rf"  \node ({dest_id})[connection] at ({src_tag_node} -| {x_ref_node}) {{}};")
    _writelines(stream, "")


def _write_edges(stream, edges):
    _writelines(stream, "  %% Connections")
    for kind, a, b, dashed in edges:
        style = "arrow" if kind == "arrow" else "match"
        opts = style + (", dashed" if dashed else "")
        # same column: trigger -> own product, straight down.
        # different column: product -> next task's main input, elbow bend.
        connector = " -- " if kind == "match" or node_col(a) == node_col(b) else " -| "
        _writelines(stream, rf"  \draw [{opts}] ({a}){connector}({b});")
    _writelines(stream, "")


def _first_content(rows, style, default):
    """First box content of any row drawn in `style` (a real example for the
    legend), or `default` if the diagram has none."""
    return next((r["content_lines"][0][0] for r in rows if r.get("style") == style), default)


def _write_legend(stream, header, rows):
    example_recipe = tex_escape(next(iter(header.values())).split(r"\REC{")[1].split("}")[0])
    example_calib = _first_content(rows, "calibproduct", r"\texttt{example}")
    example_sci = _first_content(rows, "scienceproduct", r"\texttt{example}")
    example_stat = _first_content(rows, "statcalfile", r"\STATCALIB{EXAMPLE}")
    example_ext = _first_content(rows, "extcalfile", r"\EXTCALIB{EXAMPLE}")
    example_cond, example_cond_style = next(
        ((tex, r["style"]) for r in rows for tex, conditional in r["content_lines"] if conditional),
        (r"\PROD{EXAMPLE}", "calibproduct"),
    )

    _writelines(stream, r"  %% Legend")
    begin = [
        r"  \matrix (legend) [draw, fill=gray!15, above right, row sep=0.3cm,",
        r"    column 1/.style={anchor=base},",
        r"    column 2/.style={anchor=base west}]",
        r"  at ([yshift=0cm]current bounding box.south west){%",
    ]
    end = [r"  };    %% end matrix (legend)", ""]
    with _tex_group(stream, begin, end):
        _writelines(
            stream,
            rf"    \node (leg_recipe) [recipe]{{{example_recipe}}};",
            r"    & \node {recipe}; \\",
            rf"    \node (leg_calproduct) [calibproduct]{{{example_calib}}};",
            r"    & \node{intermediate calib.\ product}; \\",
            rf"    \node (leg_sciproduct)[scienceproduct]{{{example_sci}}};",
            r"    & \node {science product}; \\",
            rf"    \node (leg_statcalfile)[statcalfile]{{{example_stat}}};",
            r"    & \node {static calib.\ file};\\",
            rf"    \node (leg_calfile)[extcalfile]{{{example_ext}}};",
            r"    & \node {external file}; \\",
            rf"    \node (leg_condproduct)[{example_cond_style}, dashed]{{{example_cond}}};",
            r"    & \node {conditionally-produced output}; \\",
            "",
            r"    \draw [arrow,fill=black] (0,0.4) -- (0,-0.3);",
            r"    & \node {processing step / main input}; \\",
            "",
            r"    \draw [connection_arrow] (-1, 0.5ex) -- (1,0.5ex) node [connection,yshift=0cm]{};",
            r"    & \node {associated-input reuse}; \\",
        )


def render(stream: TextIO, columns, header, rows, edges, node, elbow_dots, extra_dots):
    """Write the complete TikZ fragment for a built model to `stream`."""
    _write_preamble(stream)
    begin = [r"\begin{tikzpicture}[on grid=false, node distance=0.8cm]", ""]
    end = [r"\end{tikzpicture}", ""]
    with _tex_group(stream, begin, end):
        _write_recipe_matrix(stream, columns, header, rows, node, elbow_dots)
        _write_extra_dots(stream, extra_dots)
        _write_edges(stream, edges)
        _write_legend(stream, header, rows)
    _writelines(stream, r"\input{normal_style}")


def node_col(node_name):
    return node_name[len("REC"):].split("__", 1)[0]


WRAPPER_TEMPLATE = r"""% Auto-generated by generate_assomap.py -- do not hand-edit, regenerate instead.
\documentclass[tikz, margin=5mm, dvipsnames]{standalone}
\usepackage{listings}
\usepackage{hyperref}
\usepackage{xstring}
@INPUT_PATH@
\input{assomap_common}
\input{assomap_common_imports}
\input{black_style}
\input{styles_data}

\begin{document}
    \input{@FRAGMENT@}
\end{document}
"""


def render_wrapper(stream: TextIO, fragment_path, wrapper_path, style_dir):
    """Write to `stream` a standalone LaTeX document that \\input's the
    generated fragment plus the shared house style. If the style files don't live next to the wrapper,
    point \\input@path at them (relative to the wrapper, which is where
    pdflatex is expected to be run from) so both the wrapper's and the
    fragment's own \\input{black_style} etc. still resolve."""
    rel = Path(os.path.relpath(style_dir, wrapper_path.parent)).as_posix()
    if rel.startswith("../.."):
        # far away (e.g. a scratch dir): a long ../../.. chain is just noise
        rel = Path(style_dir).resolve().as_posix()
    input_path = "" if rel == "." else r"\makeatletter\def\input@path{{" + rel + r"/}}\makeatother"
    fragment = Path(os.path.relpath(fragment_path, wrapper_path.parent)).with_suffix("").as_posix()
    stream.write(WRAPPER_TEMPLATE.replace("@INPUT_PATH@", input_path).replace("@FRAGMENT@", fragment))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", help="dotted workflow path, e.g. micado.micado_spec_wkf")
    parser.add_argument("-i", "--input", type=Path, default=None,
                        help="input path to edps workflow definitions (default: looked up from the "
                             "module's top-level package via KNOWN_WORKFLOW_ROOTS, e.g. 'micado.foo' "
                             "-> micado-pipe/edps/workflow)")
    parser.add_argument("-o", "--output", type=Path, default=None,
                         help="output .tex path, or an existing directory to write the default-named "
                              "fragment into (default: "
                              "<script dir>/out/<last module component>_assomap_tikz.tex)")
    parser.add_argument("--no-wrapper", action="store_true",
                        help="don't write the standalone LaTeX wrapper (by default written next to the "
                             "fragment as <name>_assomap.tex, i.e. the output name minus '_tikz')")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    tex_dir = script_dir / "tex"  # shared house-style .tex files only
    out_dir = script_dir / "out"  # generated fragments/wrappers + pdflatex output (gitignored)
    if args.input is not None:
        workflow_root = args.input
    else:
        package = args.workflow.split(".", 1)[0]
        if package not in KNOWN_WORKFLOW_ROOTS:
            parser.error(
                f"no known workflow root for package '{package}' -- pass -i/--input explicitly "
                f"(known packages: {', '.join(sorted(KNOWN_WORKFLOW_ROOTS))})"
            )
        workflow_root = KNOWN_WORKFLOW_ROOTS[package]

    wkf = load_workflow(args.workflow, workflow_root)

    leaf = args.workflow.rsplit(".", 1)[-1].removesuffix("_wkf")
    default_name = f"{leaf}_assomap_tikz.tex"
    output = args.output
    if output is None:
        out_dir.mkdir(exist_ok=True)
        output = out_dir / default_name
    elif output.is_dir():
        output = output / default_name

    columns, header, rows, edges, node, elbow_dots, extra_dots = build_model(wkf)
    with output.open("w", encoding="utf-8") as stream:
        render(stream, columns, header, rows, edges, node, elbow_dots, extra_dots)
    print(f"wrote {output} ({len(columns)} columns, {len(rows)} rows, {len(edges)} connections)")

    if not args.no_wrapper:
        stem = output.stem
        wrapper_stem = stem.removesuffix("_tikz") if stem.endswith("_tikz") else f"{stem}_standalone"
        wrapper = output.with_name(f"{wrapper_stem}.tex")
        with wrapper.open("w", encoding="utf-8") as stream:
            render_wrapper(stream, output, wrapper, tex_dir)
        print(f"wrote {wrapper} (compile from {wrapper.parent} with: pdflatex {wrapper.name})")


if __name__ == "__main__":
    main()
