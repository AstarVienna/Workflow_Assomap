import edps

from example_workflow.micado_spec_classification import master_sflat_class
from example_workflow.micado_spec_datasources import raw_sflat_slit

from . import shared

# OUT: FIRST_ONLY
science = (edps.task("bundled_first")
           .with_recipe("bundled_first_recipe")
           .with_main_input(shared.producer, [master_sflat_class])
           .with_associated_input(raw_sflat_slit)
           .build())
