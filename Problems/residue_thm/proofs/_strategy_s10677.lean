import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrand_match_right_half_to_compose
import Problems.residue_thm.proofs.L_subst_linear_2t_minus_1

namespace Problems.residue_thm

-- Decompose into:
-- (a) integrand_match_right_half_to_compose: rewrite LHS via h = β'(2·-1) on [1/2,1]
--     (chain rule turns deriv h t into 2 · deriv β' (2t-1) a.e. on the interval),
-- (b) subst_linear_2t_minus_1: pure linear u-substitution u = 2t-1
--     on a C¹ β' over [0,1]; absorbs the factor 2 from the chain rule.
-- Chain via Eq.trans.
theorem s10677
    {Q : ℂ → ℂ} {β' h : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_right : ∀ t ∈ Set.Icc ((1/2) : ℝ) 1, h t = β' (2*t - 1)) :
    (∫ t in ((1/2) : ℝ)..1, Q (h t) * deriv h t) =
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t)  := by
  have h1 := integrand_match_right_half_to_compose (Q := Q) hβ' hh hh_right
  have h2 := subst_linear_2t_minus_1 (Q := Q) (β' := β')
  exact h1.trans h2

end Problems.residue_thm
