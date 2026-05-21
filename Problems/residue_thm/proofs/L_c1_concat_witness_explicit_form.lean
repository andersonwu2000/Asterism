import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem c1_concat_witness_explicit_form
    {a : ℂ} {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∃ αβ : ℝ → ℂ,
      ContDiffOn ℝ 1 αβ (Set.Icc 0 1) ∧
      (∀ t ∈ Set.Icc (0 : ℝ) (1/2), αβ t = α' (2*t)) ∧
      (∀ t ∈ Set.Icc (1/2 : ℝ) 1, αβ t = β' (2*t - 1)) ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, αβ t ≠ a) := by sorry

end Problems.residue_thm
