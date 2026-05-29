-- Mirror the proved non-origin-fixing transfer s11468 (q := h.trans (f.trans h.symm)), reusing
-- transfer_source/disjoint/union/target_corrected for the source/target/disjoint/union parts.
-- New content is the origin-fixing decomp data: decomp_trans_origin_fixing composes two
-- origin-fixing IsDecompOn finsets into one for an Equidecomp.trans; apply it twice
-- (f.trans h.symm, then h.trans …) to get Sf'/Sg' fixing 0 (each factor is a product of fixers).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11510

namespace Problems.Geometry.banach_tarski

def paradoxical_transfer_along_equidecomp_origin_fixing := @Problems.Geometry.banach_tarski.s11510

end Problems.Geometry.banach_tarski
