import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s71_sub_1 (a b x z : ℝ × ℝ) :
    Collinear a b x →
    Collinear a b z →
    (a.1 - b.1) * (x.2 - z.2) = (a.2 - b.2) * (x.1 - z.1) := by
  simp only [Collinear]
  intro h_abx h_abz
  linear_combination h_abz - h_abx

end Problems.sylvester_gallai
