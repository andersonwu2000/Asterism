import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_4point_descent

namespace Problems.sylvester_gallai

-- Strip the Finset envelope and `(x,y,z)` non-collinear witness: delegate the
-- geometric content to a pure 4-point Kelly descent fact on (a,b,r,c). Each of
-- a',b',c' is one of {a,b,r,c} so Q-membership follows by case dispatch on the
-- four `_ ∈ Q` hypotheses.
theorem s382 :
    ∀ (Q : Finset (ℝ × ℝ)),
      (∀ p ∈ Q, ∀ q ∈ Q, p ≠ q → ∃ r ∈ Q, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ x ∈ Q, ∀ y ∈ Q, ∀ z ∈ Q, ¬ Collinear x y z →
      ∀ a ∈ Q, ∀ b ∈ Q, ∀ c ∈ Q, ¬ Collinear a b c →
      ∀ r ∈ Q, Collinear a b r → r ≠ a → r ≠ b →
      ∃ a' ∈ Q, ∃ b' ∈ Q, ∃ c' ∈ Q, ¬ Collinear a' b' c' ∧
        ((c'.1 - a'.1) * (b'.2 - a'.2) - (c'.2 - a'.2) * (b'.1 - a'.1))^2 /
            ((b'.1 - a'.1)^2 + (b'.2 - a'.2)^2) <
        ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 /
            ((b.1 - a.1)^2 + (b.2 - a.2)^2)  := by
  intro Q _hQ _x _hx _y _hy _z _hz _hxyz a ha b hb c hc habc r hr hcabr hrna hrnb
  obtain ⟨a', b', c', ha'_in, hb'_in, hc'_in, hncol, hlt⟩ :=
    kelly_4point_descent a b r c hcabr hrna hrnb habc
  have ha'Q : a' ∈ Q := by rcases ha'_in with h|h|h|h <;> (rw [h]; assumption)
  have hb'Q : b' ∈ Q := by rcases hb'_in with h|h|h|h <;> (rw [h]; assumption)
  have hc'Q : c' ∈ Q := by rcases hc'_in with h|h|h|h <;> (rw [h]; assumption)
  exact ⟨a', ha'Q, b', hb'Q, c', hc'Q, hncol, hlt⟩

end Problems.sylvester_gallai
