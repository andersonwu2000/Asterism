-- Constancy via Ioo-interior derivative + Icc-continuity (avoids the boundary
-- trap of derivWithin on closed Icc that killed s10327). Let
-- J τ := ∫ t in 0..1, f (H τ t) * deriv (H τ) t. Split into:
--   (a) `homotopy_integral_continuous_on_icc` — J is continuous on [0,1]
--       (parametric integral of jointly continuous integrand);
--   (b) `homotopy_integral_has_deriv_at_ioo` — J' = 0 on the open (0,1)
--       (parametric Leibniz unlocks at interior τ via Icc 0 1 ∈ 𝓝 τ; the
--       boundary term vanishes by hH0/hH1 + Cauchy-Riemann);
--   (c) `endpoint_eq_of_continuous_deriv_zero_ioo` — generic real-analysis
--       closer: continuous on [0,1] + interior derivAt 0 ⇒ G 0 = G 1.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10331

namespace Problems.residue_thm

def homotopy_invariant_contour_integral := @Problems.residue_thm.s10331

end Problems.residue_thm
