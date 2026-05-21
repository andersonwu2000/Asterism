import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem concat_witness_left_eq
    {a : ℂ} {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc (0 : ℝ) (1/2),
      (if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1)) = α' (2*t) := by simp_all only [Set.mem_Icc, ne_eq, and_imp, one_div, ↓reduceIte, implies_true]

end Problems.residue_thm
