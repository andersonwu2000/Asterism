import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s56_sub_1 : ∀ (p a b c z : ℝ × ℝ),
    Collinear a b c →
    a ≠ b →
    z ∈ ({a, b, c} : Finset (ℝ × ℝ)) →
    ((a.1 - z.1) * (p.2 - z.2) - (a.2 - z.2) * (p.1 - z.1)) ^ 2 *
    ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2) =
    ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
    ((a.1 - z.1) ^ 2 + (a.2 - z.2) ^ 2) := by
  intro p a b c z hcol _hab hmem
  unfold Collinear at hcol
  simp only [Finset.mem_insert, Finset.mem_singleton] at hmem
  -- Use rw [h] instead of rcases rfl to avoid Lean eliminating `c` via subst
  rcases hmem with h | h | h
  · -- z = a: both sides vanish
    rw [h]; ring
  · -- z = b: cross-products are negatives of each other
    rw [h]; ring
  · -- z = c: use collinearity via linear_combination
    -- After rw [h], the goal has c in place of z, with c still in scope.
    -- P = 2*C*(W''+B) - 2*B*W - h_col*(X²+Y²+B) closes LHS-RHS = P*h_col by ring.
    rw [h]
    linear_combination
      (2 * ((a.1 - c.1) * (p.2 - c.2) - (a.2 - c.2) * (p.1 - c.1)) *
          ((b.1 - a.1) * (p.1 - c.1) + (b.2 - a.2) * (p.2 - c.2) +
           (a.1 - c.1) ^ 2 + (a.2 - c.2) ^ 2) -
        2 * ((a.1 - c.1) ^ 2 + (a.2 - c.2) ^ 2) *
          ((p.2 - c.2) * (b.1 - c.1) - (p.1 - c.1) * (b.2 - c.2)) -
        ((a.1 - c.1) * (b.2 - c.2) - (a.2 - c.2) * (b.1 - c.1)) *
          ((p.1 - c.1) ^ 2 + (p.2 - c.2) ^ 2 +
           (a.1 - c.1) ^ 2 + (a.2 - c.2) ^ 2)) * hcol

end Problems.sylvester_gallai
