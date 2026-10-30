"""Subworkflow with internal main/associated producers, like MUSE."""
from edps import alternative_associated_inputs, subworkflow, task

from example_workflow.micado_spec_classification import master_sflat_class
from example_workflow.micado_spec_datasources import raw_sflat, raw_wave, persistence_map


@subworkflow("fixture_subworkflow", "")
def make_subworkflow():
    base = (task("fixture_base")
            .with_recipe("fixture_base_recipe")
            .with_main_input(raw_sflat)
            .build())
    prepare = (task("fixture_prepare")
               .with_recipe("fixture_prepare_recipe")
               .with_main_input(base)
               .build())
    geometry = (task("fixture_geometry")
                .with_recipe("fixture_geometry_recipe")
                .with_main_input(raw_wave)
                .with_associated_input(base, [master_sflat_class])
                .build())
    calibrations = (alternative_associated_inputs()
                    .with_associated_input(geometry, [master_sflat_class])
                    .with_associated_input(persistence_map))
    final = (task("fixture_final")
             .with_recipe("fixture_final_recipe")
             .with_main_input(prepare)
             .with_associated_input(base, [master_sflat_class])
             .with_alternative_associated_inputs(calibrations)
             .build())
    return final, base


# Expose a consumer before its producer, and expose the consumer twice.
final, base = make_subworkflow()
final_alias = final
