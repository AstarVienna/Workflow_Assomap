# MICADO SPECMODE EDPS workflow
#
# Author: W. Kausch / University of Innsbruck
#
# Version: 0.0.1
#

from edps import data_source
from .micado_spec_classification import *

# ----------------------------------------------------------------------------
# ----------------- Defining required number of input files ------------------
# ----------------------------------------------------------------------------

# TODO: Numbers to be checked!
MIN_NUM_DARKS = 5
MIN_NUM_FLATS = 5
MIN_NUM_SFLATS = 5
MIN_NUM_SFLATSLIT = 1
MIN_NUM_SFLATS_PINH = 5
MIN_NUM_WAVE_PINH = 1
MIN_NUM_WAVE = 5
MIN_NUM_FSTD_SLIT = 1
MIN_NUM_SCI = 1
MIN_NUM_SCI_SLIT = 1
MIN_NUM_SKY = 1
MIN_NUM_FSTD = 1


# ----------------------------------------------------------------------------
# ---------------------------- RAW input files -------------------------------
# ----------------------------------------------------------------------------

raw_dark = (data_source()
            .with_classification_rule(dark_class)
            .with_min_group_size(MIN_NUM_DARKS)
            .with_match_keywords(["instrume"])
            .build())

raw_flat = (data_source()
            .with_classification_rule(img_flatfield_class)
            .with_min_group_size(MIN_NUM_FLATS)
            .with_match_keywords(["instrume"])
            .build())

raw_sflat = (data_source()
            .with_classification_rule(spectro_flatfield_class)
            .with_min_group_size(MIN_NUM_SFLATS)
            .with_match_keywords(["instrume"])
            .build())

raw_sflat_slit = (data_source()
                  .with_classification_rule(spectro_sflatslit_class)
                  .with_min_group_size(MIN_NUM_SFLATSLIT)
                  .with_match_keywords(["instrume"])
                  .build())

raw_sflat_pinh = (data_source()
            .with_classification_rule(sflat_pinhole_class)
            .with_min_group_size(MIN_NUM_SFLATS_PINH)
            .with_match_keywords(["instrume"])
            .build())

raw_wave_pinh = (data_source()
            .with_classification_rule(wave_pinhole_class)
            .with_min_group_size(MIN_NUM_WAVE_PINH)
            .with_match_keywords(["instrume"])
            .build())

raw_wave = (data_source()
            .with_classification_rule(wave_class)
            .with_min_group_size(MIN_NUM_WAVE)
            .with_match_keywords(["instrume"])
            .build())

raw_spec_fstd = (data_source()
            .with_classification_rule(spec_fstd_class)
            .with_min_group_size(MIN_NUM_FSTD)
            .with_match_keywords(["instrume"])
            .build())

raw_fstd_slit = (data_source()
            .with_classification_rule(fstd_slit_class)
            .with_min_group_size(MIN_NUM_FSTD_SLIT)
            .with_match_keywords(["instrume"])
            .build())

raw_sci_slit = (data_source()
            .with_classification_rule(sci_slit_class)
            .with_min_group_size(MIN_NUM_SCI_SLIT)
            .with_match_keywords(["instrume"])
            .build())

raw_spec_sci = (data_source()
            .with_classification_rule(spec_ssci_class)
            .with_min_group_size(MIN_NUM_SCI)
            .with_match_keywords(["instrume"])
            .build())

raw_spec_sky = (data_source()
            .with_classification_rule(spec_ssky_class)
            .with_min_group_size(MIN_NUM_SKY)
            .with_match_keywords(["instrume"])
            .build())

# ----------------------------------------------------------------------------
# ---------------------- Intermediate product files --------------------------
# ----------------------------------------------------------------------------

# Created by recipe carried out at ESO
persistence_map = (data_source()
            .with_classification_rule(persistence_map_class)
            .build())

# Bad pixel map permanently updated --> not static
ref_bp_map = (data_source()
            .with_classification_rule(ref_bp_map_class)
            .build())

# ----------------------------------------------------------------------------
# ---------------------- Static calibration files ----------------------------
# ----------------------------------------------------------------------------

ref_lamp_cat = (data_source()
                .with_classification_rule(ref_lamp_cat_class)
                .with_match_keywords(["instrume"])   # some matching is needed by edps
                .build())

ref_std_cat = (data_source()
            .with_classification_rule(ref_std_cat_class)
            .with_match_keywords(["instrume"])     # needed by edps, replace?
            .build())

ref_airg_cat = (data_source()
            .with_classification_rule(ref_airg_cat_class)
            .with_match_keywords(["instrume"])      # needed by edps, replace?
            .build())

ref_atmoline_cat = (data_source()
            .with_classification_rule(ref_atmoline_cat_class)
            .build())

psf_model = (data_source()
            .with_classification_rule(psf_model_class)
            .with_match_keywords(["instrume"])
            .build())

psf_reconstructed = (data_source()
            .with_classification_rule(psf_reconstructed_class)
            .build())

static_lsf_kernel = (data_source()
            .with_classification_rule(static_lsf_kernel_class)
            .build())

static_gdas_profile = (data_source()
            .with_classification_rule(static_gdas_profile_class)
            .build())

static_atm_profile = (data_source()
            .with_classification_rule(static_atm_profile_class)
            .build())

static_mf_parset = (data_source()
            .with_classification_rule(static_mf_parset_class)
            .build())

mf_atmo_parm = (data_source()
            .with_classification_rule(mf_atmo_parm_class)
            .build())

mf_bestfit_parm = (data_source()
            .with_classification_rule(mf_bestfit_parm_class)
            .build())

mf_telcor_parm = (data_source()
            .with_classification_rule(mf_telcor_parm_class)
            .build())

static_tw = (data_source()
                   .with_classification_rule(order_guess_tab_class)
                   .with_match_keywords(["instrume"])   # a filter may be more appropriate
                   .build())
