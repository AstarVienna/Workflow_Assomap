# workflow_assomap

Generates a TikZ "assomap" diagram (one column per task/recipe, one row per
distinct raw/product/reference data item, dot+line "match" connections where
a product is reused downstream) from a built EDPS workflow module, by
**introspecting the real `edps` Task/DataSource object model** -- not by
regexing or hand-authoring the diagram.

Originally built inside `micado-pipe/toolbox/tikz/` for the MICADO
spectroscopy workflow; moved here (2026-10-01) once it proved to work
unmodified against METIS's IFU workflow too, since it's a cross-pipeline tool
and doesn't belong nested in one pipeline's repo.

## Files

- `generate_assomap.py` -- the tool. Run with the `edps`-engine Python, e.g.:
  ```
  /Users/janus/miniconda3/envs/pyreduce_edps/bin/python3.12 generate_assomap.py micado.micado_spec_wkf
  /Users/janus/miniconda3/envs/pyreduce_edps/bin/python3.12 generate_assomap.py metis.metis_ifu_wkf
  ```
  (Must use that conda env's Python -- the pipeline repos' own `edps/`
  directories are unrelated namespace packages that shadow the real
  installed `edps` engine under the wrong interpreter/sys.path.)

  `-i/--input` overrides the workflow-definitions path; without it, the
  module's top-level package (`micado`, `metis`) is looked up in
  `KNOWN_WORKFLOW_ROOTS` in the script (pointing at sibling checkouts under
  `~/Code/pipelines/`). Add new pipelines there as needed.

- `assomap.tex` / `assomap_metis.tex` -- standalone LaTeX wrappers
  (`\documentclass[tikz,margin=5mm,dvipsnames]{standalone}`) that `\input`
  the generated `*_assomap_tikz.tex` fragment plus the shared house style:
  `assomap_common(.tex/_imports.tex)`, `black_style.tex`, `styles_data.tex`,
  `normal_style.tex`, `recipe_config.tex`. Compile with plain `pdflatex`.

- `micado_spec_assomap_tikz.tex`, `metis_ifu_assomap_tikz.tex` -- generated
  fragments, regenerate via the script rather than hand-editing.

## How output labelling works (and its limits)

A task's own recipe/workflow definition never states its output's `pro.catg`
directly. `product_output_tags()` infers it, in priority order:

1. `task.classification_rules`, populated as a side effect whenever another
   task references it with a tag, e.g.
   `.with_associated_input(dark_task, [master_dark_class])` or
   `.with_main_input(x, [tag])` -- this is how **MICADO's** workflow is
   authored, so it works there with no extra annotation.
2. `task.output_filter` (from `.with_output_filter(tag_class, ...)`), the
   task's own unambiguous declaration of what it produces.
3. A `# OUT: TAG` (or `# OUT: [TAG]` for conditional/dashed-border) comment
   written directly above the task's assignment in the workflow `.py` file --
   read straight from source via AST, since edps has no runtime concept of
   it. This is the fallback for a task with nothing downstream, or for a
   workflow style that doesn't tag associated-input calls at all.

**METIS's IFU workflow uses neither (1) with tags nor (2) for most tasks** --
its `.with_associated_input(x)` calls never pass a tag list, so most task
rows have no structural way to get a label and fall back to the task's own
Python name (`\texttt{metis_ifu_dark}` etc.) instead of a product tag like
`MASTER_DARK_IFU`. Fixing this generically would require a fragile
name-matching heuristic against `.with_input_filter(...)` lists (which only
hint at the producer by variable-naming convention, with no structural
link). Decided against that; the correct fix is adding `# OUT:` comments to
the METIS workflow source, same as MICADO's `mf_correct_task` etc. already
have. **This was left for the user to do by hand in `metis_ifu_wkf.py`** --
not done yet as of this writing.

## Key edps object-model gotchas (why the code looks the way it does)

- `task.associated_input_groups` (not `flatten_associated_inputs()`) must be
  iterated to distinguish:
  - several *separate* `.with_associated_input(x, [tag])` calls naming the
    same `x` with different tags -- each is its own group of one, i.e. an
    independent, separately-required connection (union across groups).
  - one `.with_alternatives(alternative_associated_inputs()...)` group --
    several ways to satisfy *one* input slot; only tags common to every
    alternative (with `min_ret >= 1`) are actually guaranteed (intersect
    within the group).
  Mixing these up (as an earlier version of this script did) marks
  independent required inputs as dashed/optional incorrectly.
- A main input can name only *some* of an upstream task's several output
  tags (`.with_main_input(x, [tag1, tag2])`) -- edps merges this
  indistinguishably into `x`'s shared `classification_rules` with no
  per-call record, so the literal tag list is recovered via AST
  (`parse_main_input_tags`).
- TikZ `matrix` quirks: every cell's `\node{...}` needs a trailing `;`; a
  blank line immediately before a matrix's closing `};` corrupts pgf's
  matrix-nesting state (breaks the *next* `\matrix`, e.g. the legend);
  `below=Xcm` with no explicit `of <name>` doesn't reliably chain inside a
  matrix cell; non-primary-tag connection dots are positioned with the
  `calc` library's `-|` operator against the source node's actual rendered
  height, not a fixed offset, so the connecting line stays horizontal.

## Verifying changes

Regenerate the fragment, then compile and grep/read the PDF:
```
/Users/janus/miniconda3/envs/pyreduce_edps/bin/python3.12 generate_assomap.py <module>
pdflatex -interaction=nonstopmode -halt-on-error assomap.tex   # or assomap_metis.tex
```
Check `grep -c "^!" <name>.log` is 0, then visually read the resulting PDF.

## Pending

User is adding `# OUT: TAG` comments to `metis_ifu_wkf.py` by hand; rerun the
generator against `metis.metis_ifu_wkf` afterward to confirm labels resolve
correctly. Per-task breakdown (reasoning: matched each task against the one
downstream `.with_input_filter(...)` call that names both it and a
classification tag with no other candidate producer in the file):

High confidence (unique matching `classification_rule` each):
- `ifu_lingain_task` (`metis_det_lingain`) -> `# OUT: LINEARITY_IFU, GAIN_MAP_IFU`
- `ifu_dark_task` (`metis_det_dark`) -> `# OUT: MASTER_DARK_IFU`
- `ifu_distortion_task` (`metis_ifu_distortion`) -> `# OUT: IFU_DISTORTION_TABLE`
- `ifu_wavecal_task` (`metis_ifu_wavecal`) -> `# OUT: IFU_WAVECAL`
- `ifu_rsrf_task` (`metis_ifu_rsrf`) -> `# OUT: RSRF_IFU`

Medium confidence (both share recipe `metis_ifu_reduce`, producing
different tag sets per the sci/std telluric tasks' `input_filter`s --
worth a sanity check against the recipe's actual DRLD product list):
- `ifu_std_reduce_task` -> `# OUT: IFU_STD_COMBINED`
- `ifu_sci_reduce_task` -> `# OUT: IFU_SCI_REDUCED, IFU_SCI_COMBINED`

No existing tag anywhere (nothing downstream references them with a tag,
and no corresponding `classification_rule` exists in
`metis_classification.py`) -- needs the user to pick a label, which the
`# OUT:` comment accepts as a plain string with no `classification_rule`
required:
- `ifu_calibrate_task` (`metis_ifu_calibrate`)
- `ifu_postprocess_task` (`metis_ifu_postprocess`, final `SCIENCE` product)

Already resolved via `.with_output_filter(...)`, no comment needed:
`ifu_sci_telluric_task` -> `IFU_TELLURIC`, `ifu_std_telluric_task` ->
`FLUXCAL_TAB`.
