# workflow_assomap

Generates a TikZ **association map** from an
[EDPS](https://www.eso.org/sci/software/edps.html) workflow module. The map
shows which recipes consume which raw data, calibrations and upstream
products.

The diagram is built by importing the workflow and introspecting the real
`edps` Task/DataSource objects it constructs, so it stays in sync with the
workflow code rather than being drawn by hand.

It works unmodified on different pipelines' workflows, currently MICADO
spectroscopy (`micado.micado_spec_wkf`) and METIS IFU (`metis.metis_ifu_wkf`).

## What the diagram shows

- **One column per task**, in the order tasks appear in the workflow module.
  If the first task has its own raw or reference inputs, an extra column is
  added in front of it to hold them.
- **Header row:** each task's recipe. A raw main input is shown as a title box
  above the recipe name. When the main input is another task's product, the
  recipe box has no title and an elbow arrow runs from that product.
- **One row per data item** (raw input, external/static calibration, or task
  product). Each row is created where the item first appears. Every later
  consumer is marked with a dot joined to it by a line.
- **Solid** lines and arrows are required inputs, and **dashed** ones are
  optional (`min_ret=0`).
- Product boxes are coloured as **science products** if nothing consumes them,
  or if the task name matches a pattern in `SCIENCE_PRODUCT_TASKS`.
  All other products are drawn as **intermediate calibration products**.

## Requirements

- A Python environment with the `edps` engine installed.
- The pipeline repository containing the workflow definitions.
- A LaTeX installation with TikZ (`pdflatex`).

Run the script with the Python from your `edps` environment, not a generic
`python3`.

## Usage

```sh
# 1. Generate the TikZ fragment and its standalone LaTeX wrapper (into out/)
/path/to/edps_env/bin/python generate_assomap.py metis.metis_ifu_wkf
#    -> out/metis_ifu_assomap_tikz.tex  (the diagram)
#    -> out/metis_ifu_assomap.tex       (wrapper document)

# 2. Compile the wrapper from out/, so the PDF and logs stay there too
cd out && pdflatex metis_ifu_assomap.tex
```

`out/` is gitignored: everything generated lives there. `tex/` holds only
the shared style files.

| Option | Meaning |
| --- | --- |
| `workflow` | Dotted workflow module, e.g. `metis.metis_ifu_wkf` |
| `-i`, `--input` | Directory holding the workflow definitions. Defaults to the entry for the module's top-level package in `KNOWN_WORKFLOW_ROOTS` |
| `-o`, `--output` | Output fragment path, or an existing directory (e.g. `out`) to write the default-named fragment into. Defaults to `out/<module>_assomap_tikz.tex`. The wrapper is written next to the fragment, with the same name minus `_tikz` |
| `--no-wrapper` | Write only the fragment, not the wrapper |

If the output isn't in `tex/`, the wrapper sets `\input@path` so the
shared style files are still found. Run `pdflatex`
from the wrapper's directory.

To support a new pipeline, add its package and workflow directory to
`KNOWN_WORKFLOW_ROOTS` in `generate_assomap.py`, or pass `-i`.

## Labelling products

EDPS workflows don't state a task's output product category (`pro.catg`)
directly. The generator picks a label for each product box in this order:

1. **Tags from consumers.** For example,
   `.with_associated_input(dark_task, [MASTER_DARK])` labels `dark_task`'s
   product `MASTER_DARK`.
2. **The task's own output filter**, from `.with_output_filter(...)`.
3. **An `# OUT:` comment** written directly above the task's assignment in
   the workflow source:

   ```python
   # OUT: MASTER_DARK_IFU
   ifu_dark_task = (task("metis_ifu_dark") ...)

   # OUT: IFU_SCI_REDUCED, [IFU_SCI_COMBINED]
   ifu_sci_reduce_task = (...)
   ```

   Separate several tags with commas, or put them on consecutive `# OUT:`
   lines. A tag in `[brackets]` is only produced conditionally and is drawn
   with a dashed border. The tag doesn't need a matching
   `classification_rule`. Use this for tasks with nothing downstream, or for workflows whose
   associated inputs carry no tags.
4. Otherwise, **the task's Python name** is used as the label.

## Science products

`SCIENCE_PRODUCT_TASKS` in `generate_assomap.py` lists shell-style wildcard
patterns. A task whose name matches one has its product drawn as a science
product even if a later task consumes it:

```python
SCIENCE_PRODUCT_TASKS = [
    "*_spec_sci",
    "*_spec_mf_correct",
]
```

## Tests

`example_workflow/` is a frozen copy of the MICADO spectroscopy workflow,
used as test input so the expected output doesn't change when the live
pipeline does. Run the tests with the Python from your `edps` environment:

```sh
/path/to/edps_env/bin/python -m pytest test
```

Tests that need `edps` or `pdflatex` are skipped if it isn't available.
To generate the example diagram by hand:

```sh
/path/to/edps_env/bin/python generate_assomap.py example_workflow.micado_spec_wkf -i .
```

## Files

| File | Purpose |
| --- | --- |
| `generate_assomap.py` | The generator |
| `tex/assomap_common*.tex`, `tex/black_style.tex`, `tex/styles_data.tex`, `tex/normal_style.tex`, `tex/recipe_config.tex` | Shared TikZ styles and macros |
| `example_workflow/` | Frozen MICADO spectroscopy workflow used by the tests |
| `test/` | pytest suite (`test/fixtures/` holds extra mini-workflows) |
| `out/` | Generated output: `*_assomap_tikz.tex` fragments, `*_assomap.tex` wrappers, PDFs and logs (gitignored) |
