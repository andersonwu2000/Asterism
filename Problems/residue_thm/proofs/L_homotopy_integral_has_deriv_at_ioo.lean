-- Interior parametric Leibniz + boundary vanishing.
-- (a) `parametric_leibniz_homotopy_integral` — at τ ∈ Ioo (0,1) the τ-derivative
--     of J τ := ∫ t, f(H τ t) * ∂_t H(τ,t) equals ∫ t, ∂_τ (f(H τ' t) * ∂_t H(τ',t)) τ
--     (Icc 0 1 ∈ 𝓝 τ unlocks Mathlib's parametric integral Leibniz; both factors are
--     C¹ in (τ,t) since `hf` is analytic and `hH` is ContDiffOn ℝ 2).
-- (b) `homotopy_tau_partial_integrates_to_zero` — the integral of the τ-partial is 0:
--     Cauchy–Riemann gives ∂_τ(f(H τ' t) * ∂_t H) = ∂_t(f(H τ' t) * ∂_τ H), then FTC
--     in t collapses to f(H τ 1)·∂_τ H(τ,1) − f(H τ 0)·∂_τ H(τ,0), which vanishes
--     because hH0/hH1 force H τ' 0 and H τ' 1 to be constant in τ'.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10332

namespace Problems.residue_thm

def homotopy_integral_has_deriv_at_ioo := @Problems.residue_thm.s10332

end Problems.residue_thm
