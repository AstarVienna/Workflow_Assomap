from edps import task

from example_workflow.micado_spec_classification import master_dark_class
from example_workflow.micado_spec_datasources import raw_wave

from . import shared

# OUT: SECOND_ONLY
science = (task("bundled_second")
           .with_recipe("bundled_second_recipe")
           .with_main_input(raw_wave)
           .with_associated_input(shared.producer, [master_dark_class])
           .build())
