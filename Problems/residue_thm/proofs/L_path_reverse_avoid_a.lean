import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- path_reverse_avoid_a: if β avoids a on [0,1], so does t ↦ β(1-t)
theorem path_reverse_avoid_a
    {a : ℂ} {β : ℝ → ℂ}
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
    ∀ t ∈ Set.Icc (0 : ℝ) 1, β (1 - t) ≠ a := by
  intro t ht
  apply hβ_avoid
  constructor
  · linarith [ht.2]
  · linarith [ht.1]

end Problems.residue_thm
