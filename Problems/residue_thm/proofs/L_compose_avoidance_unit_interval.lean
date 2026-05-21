import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem compose_avoidance_unit_interval
    {a : ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    ∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a := by simp_all only [Set.mem_Icc, ne_eq, and_imp, Function.comp_apply, not_false_eq_true, implies_true]

end Problems.residue_thm
