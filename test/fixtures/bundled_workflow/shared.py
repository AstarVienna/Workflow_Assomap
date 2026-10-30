from edps import task

from example_workflow.micado_spec_datasources import raw_sflat

# OUT: EXTRA_PRODUCT
producer = (task("bundled_producer")
            .with_recipe("bundled_producer_recipe")
            .with_main_input(raw_sflat)
            .build())
