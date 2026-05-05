import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s71_sub_2 (a b x z p : ℝ × ℝ) :
    (a.1 - b.1) * (x.2 - z.2) = (a.2 - b.2) * (x.1 - z.1) →
    x.1 ≠ z.1 →
    Collinear x p z →
    (a.1 - b.1) * (p.2 - z.2) = (a.2 - b.2) * (p.1 - z.1) := by
  simp only [Collinear]
  intro h_slope h_ne h_xpz
  have hne : x.1 - z.1 ≠ 0 := sub_ne_zero.mpr h_ne
  have key : (x.1 - z.1) * ((a.1 - b.1) * (p.2 - z.2) - (a.2 - b.2) * (p.1 - z.1)) = 0 := by
    linear_combination (a.1 - b.1) * h_xpz + (p.1 - z.1) * h_slope
  rcases mul_eq_zero.mp key with h | h
  · exact absurd h hne
  · linarith

end Problems.sylvester_gallai
