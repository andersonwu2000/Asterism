import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem concat_piecewise_avoid_wrap
    {a : ℂ} {α' β' : ℝ → ℂ}
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a) :
    ∀ t ∈ Set.Icc (0 : ℝ) 1,
      (fun t : ℝ => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1)) t ≠ a := by grind

end Problems.residue_thm
