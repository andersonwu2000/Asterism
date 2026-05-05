import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s56_sub_2 : ∀ (p a b c z : ℝ × ℝ),
    Collinear a b c →
    a ≠ b →
    z ∈ ({a, b, c} : Finset (ℝ × ℝ)) →
    ((b.1 - z.1) * (p.2 - z.2) - (b.2 - z.2) * (p.1 - z.1)) ^ 2 *
    ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2) =
    ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
    ((b.1 - z.1) ^ 2 + (b.2 - z.2) ^ 2) := by
  intro p a b c z hcol _ hz
  simp only [Collinear] at hcol
  -- Use mem_insert.mp explicitly (not simp+rcases rfl) to avoid subst eliminating c
  rcases Finset.mem_insert.mp hz with rfl | hz'
  · -- z = a: LHS inner = (a.2-b.2)*(p.1-b.1) - (a.1-b.1)*(p.2-b.2) = RHS inner
    ring
  · rcases Finset.mem_insert.mp hz' with rfl | hz''
    · -- z = b: b.1-b.1 = 0, b.2-b.2 = 0, both sides vanish
      ring
    · -- z ∈ {c}: use rw (not subst) to keep c in scope
      rw [Finset.mem_singleton] at hz''
      -- hz'' : z = c; rw rewrites z→c in goal only, c stays in context
      rw [hz'']
      -- Goal: ((b.1-c.1)*(p.2-c.2)-(b.2-c.2)*(p.1-c.1))²*|a-b|² = ((p-b)×(a-b))²*|b-c|²
      -- Coefficient from: LHS-RHS = -[(B×P)(P·A)+(A×P)(P·B)]*(A×B)
      -- where A=a-b, B=b-c, P=p-b, A×B = hcol_lhs - hcol_rhs
      linear_combination
        (-((b.1 - c.1) * (p.2 - b.2) - (b.2 - c.2) * (p.1 - b.1)) *
          ((p.1 - b.1) * (a.1 - b.1) + (p.2 - b.2) * (a.2 - b.2)) -
          ((a.1 - b.1) * (p.2 - b.2) - (a.2 - b.2) * (p.1 - b.1)) *
          ((p.1 - b.1) * (b.1 - c.1) + (p.2 - b.2) * (b.2 - c.2))) * hcol

end Problems.sylvester_gallai
