# MICADO SPECMODE EDPS workflow
#
# Author: W. Kausch / University of Innsbruck
#
# Version: 0.0.1
#

from . import micado_spec_keywords as kwd

# Check for instrument
def is_micado(f):
    return f[kwd.instrume] == "MICADO"

# Check for LSS LM band mode
def is_specmode(f):
    return f[kwd.dpr_tech] == "SPEC"

