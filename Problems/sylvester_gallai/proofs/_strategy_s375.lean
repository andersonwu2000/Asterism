import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_collinear

namespace Problems.sylvester_gallai

-- Contrapositive reduction: assume no ordinary line and derive that all triples
-- in P are collinear, contradicting the non-collinear hypothesis.
-- Sub-goal `kelly_collinear` carries the geometric content (Kelly's distance
-- minimisation argument); the patch only does push_neg + apply + hit hypothesis.
theorem s375 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ q ∈ P, p ≠ q ∧ ∀ r ∈ P, Collinear p q r → r = p ∨ r = q  := by
  intro P hP
  by_contra hno
  push_neg at hno
  obtain ⟨a, ha, b, hb, c, hc, hncab⟩ := hP
  exact hncab (kelly_collinear P hno a ha b hb c hc)

end Problems.sylvester_gallai
