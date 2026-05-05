import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Backward
theorem s6_sub_2 : ∀ (P : Finset (ℝ × ℝ)) (p a b : ℝ × ℝ),
    p ∈ P → a ∈ P → b ∈ P → a ≠ b → ¬ Collinear p a b →
    (∀ q ∈ P, ∀ c ∈ P, ∀ d ∈ P, c ≠ d → ¬ Collinear q c d →
      ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1)) ^ 2 *
        ((c.1 - d.1) ^ 2 + (c.2 - d.2) ^ 2) ≤
      ((q.1 - c.1) * (d.2 - c.2) - (q.2 - c.2) * (d.1 - c.1)) ^ 2 *
        ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2)) →
    ∀ r ∈ P, Collinear a b r → r = a ∨ r = b := by sorry

end Problems.sylvester_gallai
