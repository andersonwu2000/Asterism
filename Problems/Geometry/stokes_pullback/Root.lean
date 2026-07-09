-- Mirror of Library.Geometry.Manifold.MExtDeriv.contMDiff_mextDerivFun for the boundary pullback.
-- At each p₀: Bundle.Trivialization.contMDiffAt_section_iff reduces the section's smoothness to
-- ContMDiffAt of the trivialization read; pullback_fixed_chart_contmdiff_at (fed the boundary
-- inclusion's smoothness bdry_val_contmdiff) gives smoothness of the fixed-basepoint chart formula;
-- pullback_triv_read identifies the two near p₀; congr_of_eventuallyEq glues.
import Mathlib
import Problems.Geometry.stokes_pullback.Defs
import Problems.Geometry.stokes_pullback.proofs._strategy_s11702

namespace Problems.Geometry.stokes_pullback

def main := @Problems.Geometry.stokes_pullback.s11702

end Problems.Geometry.stokes_pullback
