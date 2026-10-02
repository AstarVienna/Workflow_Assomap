# MICADO SPECMODE EDPS workflow
#
# Version: 0.0.1
#

from edps import classification_rule
from . import micado_spec_rules as rules
from . import micado_spec_keywords as kwd

# ----------------------------------------------------------------------------
# ------------------------- Classification rules -----------------------------
# ----------------------------------------------------------------------------

# Define sets of keywords for easier classification / briefer description
# These sets replace individual keyword lists in classifications (cf. kmos_classification.py)
micado = {kwd.instrume: "MICADO"}
mic_img_science = {**micado, kwd.dpr_catg: "SCIENCE", kwd.dpr_tech: "IMAGE,SI"}
mic_img_calibs = {**micado, kwd.dpr_catg: "CALIB", kwd.dpr_tech: "IMAGE,SI"}
mic_spec_science = {**micado, kwd.dpr_catg: "SCIENCE", kwd.dpr_tech: "SPEC"}
mic_spec_calibs = {**micado, kwd.dpr_catg: "CALIB", kwd.dpr_tech: "SPEC"}


# ----------------------------------------------------------------------------
# RAW data classes -----------------------------------------------------------
# ----------------------------------------------------------------------------

# raw DARK
dark_class = classification_rule("DARK", {**micado, **mic_img_calibs, kwd.dpr_type:"DARK"})
# raw FLAT image
img_flatfield_class = classification_rule("FLAT",{**micado, **mic_img_calibs, kwd.dpr_type:"FLAT,LAMP"})
# raw FLAT spectro
spectro_flatfield_class = classification_rule("SFLAT_RAW", {**micado, **mic_spec_calibs, kwd.dpr_type:"SFLAT"})
# raw slit image: SFLATSLIT
spectro_sflatslit_class = classification_rule("SFLAT_SLIT_RAW", {**micado, **mic_spec_calibs, kwd.dpr_type:"SFLATSLIT"})
# raw PINHOLE SFLATS
sflat_pinhole_class = classification_rule("SFLAT_PINH_RAW", {**micado, **mic_spec_calibs, kwd.dpr_type:"SFLAT_PINH"}) # FLAT,PINH
# raw PINHOLE WAVE
wave_pinhole_class = classification_rule("WAVE_PINH_RAW", {**micado, **mic_spec_calibs, kwd.dpr_type:"WAVE_PINH"})  # WAVE,PINH
# raw SPEC_WAVE
wave_class = classification_rule("WAVE_RAW", {**micado, **mic_spec_calibs, kwd.dpr_type:"WAVE"})
# raw FSTD spec
spec_fstd_class = classification_rule("FSTD_RAW", {**micado, **mic_spec_calibs, kwd.dpr_type:"FLUX"})
# raw FLUXSTD slit img
fstd_slit_class = classification_rule("FSTD_SLIT_RAW", {**micado, **mic_spec_calibs, kwd.dpr_type:"FSTDSLIT"})

# raw SCIENCE spec
spec_ssci_class = classification_rule("SSCI_RAW", {**micado, **mic_spec_science, kwd.dpr_type:"OBJECT",})
# raw SCIENCE slit img
sci_slit_class = classification_rule("SCI_SLIT_RAW", {**micado, **mic_spec_calibs, kwd.dpr_type:"SCISLIT",})
# raw SKY_spec
spec_ssky_class = classification_rule("SSKY_RAW", {**micado, **mic_spec_science, kwd.dpr_type:"SKY",})

# ----------------------------------------------------------------------------
# MASTER and intermediate calibrations classes -------------------------------
# ----------------------------------------------------------------------------

master_dark_class = classification_rule("MASTER_DARK", {**micado, **mic_img_calibs, kwd.pro_catg:"MASTER_DARK"})
master_flat_class = classification_rule("MASTER_FLAT", {**micado, **mic_img_calibs, kwd.pro_catg:"MASTER_FLAT"})
master_sflat_class = classification_rule("MASTER_SFLAT", {**micado, **mic_spec_calibs, kwd.pro_catg:"MASTER_SFLAT"})
master_trace_wave_class = classification_rule("MASTER_TW", {**micado, **mic_spec_calibs, kwd.pro_catg:"MASTER_TW"})
master_sflat_norm_class = classification_rule("MASTER_SFLAT_NORM", {**micado, **mic_spec_calibs, kwd.pro_catg:"MASTER_SFLAT_NORM"})
master_sflat_blaze_class = classification_rule("MASTER_SFLAT_BLAZE", {**micado, **mic_spec_calibs, kwd.pro_catg:"MASTER_SFLAT_BLAZE"})
int_spec_flux_class = classification_rule("SPEC_FLUX_RESPONSE", {**micado, **mic_spec_calibs, kwd.pro_catg:"SPEC_FLUX_RESPONSE"})
int_mf_atmoparam_class = classification_rule("MF_ATMOS_PARM", {**micado, **mic_spec_calibs, kwd.pro_catg:"MF_ATMOS_PARM"})
int_mf_bfparam_class = classification_rule("MF_BEST_FIT_PARM", {**micado, **mic_spec_calibs, kwd.pro_catg:"MF_BEST_FIT_PARM"})
int_mf_bfmodel_class = classification_rule("MF_BEST_FIT_MODEL", {**micado, **mic_spec_calibs, kwd.pro_catg:"MF_BEST_FIT_MODEL"})
int_mf_calctrans_data_class = classification_rule("MF_TELLURIC_DATA", {**micado, **mic_spec_calibs, kwd.pro_catg:"MF_TELLURIC_DATA"})
int_mf_calctrans_corr_class = classification_rule("MF_TELLURIC_CORR", {**micado, **mic_spec_calibs, kwd.pro_catg:"MF_TELLURIC_CORR"})
# ----------------------------------------------------------------------------
# FINAL product data classes ------------------------------------------------
# ----------------------------------------------------------------------------

final_spec_sci_2d_class = classification_rule("SPEC_SCI_2D", {**micado, **mic_spec_science, kwd.pro_catg:"SPEC_SCI_2D"})
final_spec_sci_1d_class = classification_rule("SPEC_SCI_1D", {**micado, **mic_spec_science, kwd.pro_catg:"SPEC_SCI_1D"})
final_spec_sci_trace_wave_class = classification_rule("SPEC_SCI_TW", {**micado, **mic_spec_science, kwd.pro_catg:"SPEC_SCI_TW"})
final_spec_sci_telluric_class = classification_rule("SPEC_SCI_1D_TELLURIC", {**micado, **mic_spec_science, kwd.pro_catg:"SPEC_SCI_TELLURIC"})
final_spec_sci_telluric_class = classification_rule("SPEC_SCI_2D_TELLURIC", {**micado, **mic_spec_science, kwd.pro_catg:"SPEC_SCI_TELLURIC"})

# ----------------------------------------------------------------------------
# Static and dynamic data classes --------------------------------------------
# ----------------------------------------------------------------------------

# Persistence map (comes from a recipe executed at ESO)  
persistence_map_class = classification_rule("PERSISTENCE_MAP", {"pro.catg":"PERSISTENCE_MAP"})
# Bad pixel map
ref_bp_map_class = classification_rule("REF_BP_MAP", {"pro.catg":"PERSISTENCE_MAP"})
# Line list for wavecal lamps (penray lamps and/or FPI)
ref_lamp_cat_class = classification_rule("REF_LAMP_CAT", {"pro.catg":"REF_LAMP_CAT"})
# Flux standard star catalogue
ref_std_cat_class = classification_rule("REF_STD_CAT", {"pro.catg":"REF_STD_CAT"})
# Reference line list for airglow emission (e.g. Rousselot et al, Noll et al)
ref_airg_cat_class = classification_rule("REF_AIRG_CAT", {"pro.catg":"REF_AIRG_CAT"})
# Line list atmospheric absorption lines (e.g. HITRAN)
ref_atmoline_cat_class = classification_rule("REF_ATMOLINE_CAT", {"pro.catg":"REF_ATMOLINE_CAT"})
# General PSF model
psf_model_class = classification_rule("PSF_MODEL", {"pro.catg":"PSF_MODEL"})
# Reconstructed PSF from PSFR pipeline
psf_reconstructed_class = classification_rule("PSF_REC", {"pro.catg":"PSF_REC"})
# LSF model for molecfit
static_lsf_kernel_class = classification_rule("LSF_KERNEL_MODEL", {"pro.catg":"LSF_KERNEL_MODEL"})
# GDAS profile used for molecfit
static_gdas_profile_class = classification_rule("GDAS", {kwd.pro_catg:"GDAS"})
# Atmospheric profile used for molecfit
static_atm_profile_class = classification_rule("ATM_PROFILE", {kwd.pro_catg:"ATM_PROFILE"})
# Molecfit starting paramter set
static_mf_parset_class = classification_rule("MF_PARAMETERS_START", {kwd.pro_catg:"MF_PARAMETERS_START"})
# Molecfit atmospheric paramter set
mf_atmo_parm_class = classification_rule("MF_ATMOS_PARM", {kwd.pro_catg:"MF_ATMOS_PARM"})
# Molecfit atmospheric paramter set
mf_bestfit_parm_class = classification_rule("MF_BEST_FIT_PARM", {kwd.pro_catg:"MF_BEST_FIT_PARM"})
# Molecfit telluric correction paramter set
mf_telcor_parm_class = classification_rule("MF_TELLURIC_CORR", {kwd.pro_catg:"MF_TELLURIC_CORR"})
# Order guess table
order_guess_tab_class = classification_rule("STATIC_TW", {"pro.catg": "STATIC_TW"})
