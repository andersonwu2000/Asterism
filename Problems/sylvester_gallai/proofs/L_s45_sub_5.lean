import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s45_sub_5 : ∀ (x y da di : ℝ),
    0 < da → 0 < di → x / da ≤ y / di → x * di ≤ y * da := by
  intro x y da di hda hdi h
  rwa [div_le_div_iff₀ hda hdi] at h

end Problems.sylvester_gallai
