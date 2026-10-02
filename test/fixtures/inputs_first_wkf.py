"""Minimal workflow whose *first* task has raw/reference associated inputs of
its own, so generate_assomap must add a leading inputs-only column for them
(the example MICADO workflow's first task, micado_gen_dark, has none).

Reuses the example workflow's data sources; needs the repo root on sys.path.
"""
from edps import task

from example_workflow.micado_spec_classification import master_sflat_class
from example_workflow.micado_spec_datasources import raw_sflat, raw_sflat_slit, raw_wave, persistence_map

flat_task = (task("fixture_flat")
             .with_main_input(raw_sflat)
             .with_associated_input(raw_sflat_slit)
             .with_associated_input(persistence_map, min_ret=0)
             .with_recipe("fixture_flat_recipe")
             .build())

wave_task = (task("fixture_wave")
             .with_main_input(raw_wave)
             .with_associated_input(flat_task, [master_sflat_class])
             .with_recipe("fixture_wave_recipe")
             .build())
