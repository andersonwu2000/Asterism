import Mathlib
import Problems.Minif2f.aime_1983_p9.Defs
import Problems.Minif2f.aime_1983_p9.proofs.L_am_gm_core
import Problems.Minif2f.aime_1983_p9.proofs.L_pos_xsx

namespace Problems.Minif2f.aime_1983_p9

-- Decompose via t := x * sin x. Reduce to (a) positivity of x * sin x on (0, π)
-- and (b) the AM-GM-style core inequality 12 ≤ (9 t² + 4) / t for t > 0.
-- Algebraic glue: x² * (sin x)² = (x * sin x)², so the parent goal rewrites to
-- 12 ≤ (9 (x sin x)² + 4) / (x sin x), then the core lemma closes it.
theorem s534 : ∀ (x : ℝ) (h₀ : 0 < x ∧ x < Real.pi), 12 ≤ (9 * (x ^ 2 * Real.sin x ^ 2) + 4) / (x * Real.sin x)  := by
  intro x h₀
  have h_pos := pos_xsx x h₀
  have h_core := am_gm_core (x * Real.sin x) h_pos
  have heq : x ^ 2 * Real.sin x ^ 2 = (x * Real.sin x) ^ 2 := by ring
  rw [heq]
  exact h_core

end Problems.Minif2f.aime_1983_p9
