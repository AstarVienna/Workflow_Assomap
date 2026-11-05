"""Tasks for association only, Python recipe wrappers, and product copying."""
from edps import copy_all, task

from example_workflow.micado_spec_datasources import raw_sflat

association = (task("fixture_association")
               .with_main_input(raw_sflat)
               .build())

wrapper = (task("fixture_wrapper")
           .with_function(copy_all, recipes=["wrapped_first", "wrapped_second"])
           .with_main_input(association)
           .build())

forward = (task("fixture_forward")
           .with_function(copy_all)
           .with_main_input(wrapper)
           .build())
