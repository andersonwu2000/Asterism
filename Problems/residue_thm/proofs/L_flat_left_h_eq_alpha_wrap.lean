import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_concat_ftc_left_half

namespace Problems.residue_thm

-- flat_left_h_eq_alpha_wrap: delegates to flat_concat_ftc_left_half (s10663);
-- for t ∈ [0,1/2] the piecewise if-integrand collapses to the α'-branch and
-- FTC+linear-substitution gives α'(0) + ∫₀ᵗ 2·derivWithin α'(2s) ds = α'(2t).
theorem flat_left_h_eq_alpha_wrap
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc (0:ℝ) (1/2),
      α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = α' (2*t) := by
  exact flat_concat_ftc_left_half hα' hβ' h_match hα'_deriv hβ'_deriv

end Problems.residue_thm
