import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_subst_alpha_step_wrapper

namespace Problems.residue_thm

-- Reduce to abstract change-of-variables wrapper `subst_alpha_step_wrapper`
-- (mirrors the open sibling `int_left_half_h_eq_alpha` shape). The wrapper
-- consumes only `hα'`, `hh`, `hh_left`; remaining parent hypotheses are
-- unused at this layer. The Builder will close the wrapper via the open
-- sibling once it lands; meanwhile the wrapper is a strictly-simpler
-- sub-goal carrying no `Q`-analyticity / `β'` / endpoint-derivative data.
theorem s10675
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0)
    {h : ℝ → ℂ}
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1/2), h t = α' (2*t)) :
    (∫ t in (0:ℝ)..(1/2:ℝ), Q (h t) * deriv h t) =
      (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t)  := by
  exact subst_alpha_step_wrapper hα' hh hh_left

end Problems.residue_thm
