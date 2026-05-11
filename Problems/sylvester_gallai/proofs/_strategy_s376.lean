import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_contradiction

namespace Problems.sylvester_gallai

-- Contrapositive reduction: fix a triple a,b,c ∈ P and by_contra get an
-- explicit non-collinear witness, then the geometric content (Kelly's
-- minimisation) is concentrated in `kelly_contradiction`, whose conclusion
-- is `False` with a concrete non-collinear triple as hypothesis — strictly
-- simpler than the universally quantified parent.
theorem s376 : ∀ (P : Finset (ℝ × ℝ)),
    (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
    ∀ a ∈ P, ∀ b ∈ P, ∀ c ∈ P, Collinear a b c  := by
  intro P hP a haP b hbP c hcP
  by_contra hnc
  exact kelly_contradiction P hP a haP b hbP c hcP hnc

end Problems.sylvester_gallai
