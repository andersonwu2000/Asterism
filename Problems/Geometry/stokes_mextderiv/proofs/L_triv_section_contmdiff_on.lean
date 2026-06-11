-- Direct sorry-free proof: the trivialization at x₀ has baseSet defeq to (chartAt H x₀).source,
-- so the trivialized read of the smooth section φ is ContMDiffOn there by mathlib's
-- Trivialization.contMDiffOn_section_iff applied to φ.contMDiff; the goal's
-- continuousLinearMapAt wrapper agrees pointwise via continuousLinearMapAt_apply_of_mem.
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11687

namespace Problems.Geometry.stokes_mextderiv

def triv_section_contmdiff_on := @Problems.Geometry.stokes_mextderiv.s11687

end Problems.Geometry.stokes_mextderiv
