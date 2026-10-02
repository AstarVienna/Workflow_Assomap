# MICADO SPECMODE EDPS workflow
#
# Version: 0.0.1
#

"""MICADO SPECMODE EDPS workflow"""
from edps import SCIENCE, QC1_CALIB, QC0, CALCHECKER
from edps import task, data_source, classification_rule, alternative_associated_inputs
from .micado_spec_classification import *
from .micado_spec_datasources import *
from .micado_spec_task_functions import *


# ----------------------------------------------------------------------------
# ------------------------ Processing tasks ----------------------------------
# ----------------------------------------------------------------------------

dark_task = (task('micado_gen_dark')
            .with_main_input(raw_dark)
            .with_recipe("mcd_det_dark")
            .with_meta_targets([QC1_CALIB])
            .build())

image_flatfielding_task = (
    task('micado_img_flatfield')
    .with_main_input(raw_flat)
    .with_associated_input(dark_task, [master_dark_class])
    .with_recipe("mcd_img_flat")
    .with_meta_targets([QC1_CALIB])
    .build()
)

spectro_flatfielding_task = (
    task('micado_spec_flatfield')
    .with_main_input(raw_sflat)
    .with_associated_input(raw_sflat_slit)
    .with_associated_input(persistence_map, min_ret=0) # min_ret=0 --> optional input
    .with_associated_input(dark_task, [master_dark_class]) # min_ret=0 --> optional input
    .with_associated_input(image_flatfielding_task, [master_flat_class], min_ret=0) # min_ret=0 --> optional input
    .with_associated_input(ref_bp_map, min_ret=0) # min_ret=0 --> optional input
    .with_recipe("mcd_spec_flat")
    .with_meta_targets([QC1_CALIB])
    .build()
)

spectro_wavelength_calib_task = (task('micado_spec_wave')
            .with_main_input(raw_wave)
            .with_associated_input(raw_sflat_pinh, min_ret=0)
            .with_associated_input(persistence_map, min_ret=0) # min_ret=0 --> optional input
            .with_associated_input(dark_task, [master_dark_class]) # min_ret=0 --> optional input
            .with_associated_input(ref_bp_map, min_ret=0) # min_ret=0 --> optional input 
            .with_associated_input(static_tw)
            .with_associated_input(spectro_flatfielding_task, [master_sflat_class])
            .with_associated_input(ref_lamp_cat)
            .with_recipe("mcd_spec_wave")
            .with_meta_targets([QC1_CALIB])
            .build())

spectro_flux_calibration_task = (task('micado_spec_flux')
            .with_main_input(raw_spec_fstd)
            .with_associated_input(raw_fstd_slit)  
            .with_associated_input(persistence_map, min_ret=0) # min_ret=0 --> optional input
            .with_associated_input(dark_task, [master_dark_class], min_ret=0) # min_ret=0 --> optional input
            .with_associated_input(ref_bp_map, min_ret=0) # min_ret=0 --> optional input 
            .with_associated_input(psf_model)
            .with_associated_input(psf_reconstructed, min_ret=0) # min_ret=0 --> optional input
            #.with_associated_input(spectro_flatfielding_task, [master_sflat_class])
            .with_associated_input(spectro_wavelength_calib_task, [master_trace_wave_class, master_sflat_norm_class, master_sflat_blaze_class])
            .with_associated_input(ref_std_cat)
            # .with_associated_input(ref_airg_cat)
            .with_recipe("mcd_spec_flux")
            .with_meta_targets([QC1_CALIB])
            .build())

spectro_science_calibration_task = (task('micado_spec_sci')
            .with_main_input(raw_spec_sci)
            .with_associated_input(raw_sci_slit)  # TODO: Check # of input
            .with_associated_input(raw_spec_sky, min_ret=0)  # TODO: Check # of input // Optional input if not nodding is chosen
            .with_associated_input(persistence_map, min_ret=0) # min_ret=0 --> optional input 
            .with_associated_input(dark_task, [master_dark_class], min_ret=0) # min_ret=0 --> optional input
            .with_associated_input(ref_bp_map, min_ret=0) # min_ret=0 --> optional input
            # .with_associated_input(ref_airg_cat)
            # .with_associated_input(spectro_flatfielding_task, [master_sflat_class])
            .with_associated_input(spectro_wavelength_calib_task, [master_trace_wave_class, master_sflat_norm_class, master_sflat_blaze_class])
            .with_associated_input(spectro_flux_calibration_task, [int_spec_flux_class])
            .with_recipe("mcd_spec_sci")
            .with_meta_targets([QC1_CALIB])
            .build())

# Include branch to let user decide whether science or std data as input
mf_model_task = (task("micado_spec_mf_model")
            .with_main_input(spectro_science_calibration_task, [final_spec_sci_1d_class])
            .with_associated_input(ref_atmoline_cat, min_ret=0)
            .with_associated_input(static_lsf_kernel, min_ret=0)
            .with_associated_input(static_mf_parset, min_ret=0)
            .with_associated_input(static_gdas_profile, min_ret=0)
            .with_associated_input(static_atm_profile, min_ret=0)
            .with_recipe("mcd_spec_mf_model")
            .with_meta_targets([QC1_CALIB])
            .build())

#OUT: MF_TELLURIC_DATA
mf_calctrans_task = (task("micado_spec_mf_calctrans")
            .with_main_input(mf_model_task, [int_mf_atmoparam_class, int_mf_bfparam_class, int_mf_bfmodel_class])
            .with_associated_input(spectro_science_calibration_task, [final_spec_sci_1d_class])
            .with_associated_input(ref_atmoline_cat, min_ret=0)
            .with_associated_input(static_lsf_kernel, min_ret=0)
            .with_recipe("mcd_spec_mf_calctrans")
            .with_meta_targets([QC1_CALIB])
            .build())

mf_correct_alternatives = (alternative_associated_inputs()
            .with_associated_input(spectro_science_calibration_task, [final_spec_sci_1d_class, final_spec_sci_2d_class, final_spec_sci_trace_wave_class])
            .with_associated_input(spectro_science_calibration_task, [final_spec_sci_1d_class]))

#OUT: SPEC_SCI_1D_TELL, [SPEC_SCI_2D_TELL]
mf_correct_task = (task("micado_spec_mf_correct")
            .with_main_input(mf_calctrans_task, [int_mf_calctrans_corr_class])
            .with_alternatives(mf_correct_alternatives)
            .with_recipe("mcd_spec_mf_correct")
            .with_meta_targets([QC1_CALIB])
            .build())
