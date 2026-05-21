import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_right_half_deriv_value_eq_on_ioo
import Problems.residue_thm.proofs.L_right_half_path_value_eq_on_ioo

namespace Problems.residue_thm

-- Pointwise on `Ioo (1/2) 1`, rewrite the integrand via two sub-goals:
-- `right_half_path_value_eq_on_ioo` (γ t = β' (2t-1)) and
-- `right_half_deriv_value_eq_on_ioo` (deriv γ t = 2 * derivWithin β' (Icc 0 1) (2t-1)),
-- then close by congruence (rw the two equalities under `Q _ * _`).
theorem s10679
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
    Set.EqOn
      (fun t : ℝ =>
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t)
      (fun t : ℝ => Q (β' (2*t - 1)) * (2 * derivWithin β' (Set.Icc 0 1) (2*t - 1)))
      (Set.Ioo (1/2 : ℝ) 1)  := by
  have h_path :=
    right_half_path_value_eq_on_ioo (β' := β') hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_deriv :=
    right_half_deriv_value_eq_on_ioo (β' := β') hα' hβ' h_match hα'_deriv hβ'_deriv
  intro t ht
  change Q _ * _ = Q _ * _
  rw [h_path t ht, h_deriv t ht]

end Problems.residue_thm
