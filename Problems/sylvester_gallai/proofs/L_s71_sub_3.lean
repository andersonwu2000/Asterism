import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s71_sub_3 : ∀ (a b z p : ℝ × ℝ),
    Collinear a b z →
    (a.1 - b.1) * (p.2 - z.2) = (a.2 - b.2) * (p.1 - z.1) →
    Collinear a b p := by
  intro a b z p h_abz h_pz
  simp only [Collinear] at *
  linear_combination h_abz - h_pz

end Problems.sylvester_gallai
