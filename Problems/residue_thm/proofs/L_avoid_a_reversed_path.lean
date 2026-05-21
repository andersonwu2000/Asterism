import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- avoid_a_reversed_path: β avoids a on [0,1] implies β∘(1-·) avoids a on [0,1]
-- Since t ∈ [0,1] implies 1-t ∈ [0,1], apply hβ_avoid at 1-t directly.
theorem avoid_a_reversed_path
    {a : ℂ} {β : ℝ → ℂ}
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
    ∀ t ∈ Set.Icc (0 : ℝ) 1, β (1 - t) ≠ a := by
  intro t ht
  exact hβ_avoid (1 - t) ⟨by linarith [ht.2], by linarith [ht.1]⟩

end Problems.residue_thm
