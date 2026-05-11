import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_exists_smaller_perp_triple

namespace Problems.sylvester_gallai

-- Reduce to: given a non-collinear triple (a,b,c) ∈ Q³ with Q collinearity-closed,
-- exhibit some (a',b',c') ∈ Q³ non-collinear with strictly smaller squared
-- perp-distance ratio. The minimum hypothesis hmin then gives ≤ in one direction,
-- contradicting < produced by the sub-goal — closer by `linarith`.
-- The sub-goal is strictly simpler: it drops the parent's universally quantified
-- minimum hypothesis and replaces it with a concrete existential, packaging the
-- full Kelly foot-of-perpendicular construction in one abstract statement.
theorem s379 :
    ∀ (Q : Finset (ℝ × ℝ)),
      (∀ p ∈ Q, ∀ q ∈ Q, p ≠ q → ∃ r ∈ Q, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ x ∈ Q, ∀ y ∈ Q, ∀ z ∈ Q, ¬ Collinear x y z →
      ∀ a ∈ Q, ∀ b ∈ Q, ∀ c ∈ Q, ¬ Collinear a b c →
        (∀ a' ∈ Q, ∀ b' ∈ Q, ∀ c' ∈ Q, ¬ Collinear a' b' c' →
          ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 /
              ((b.1 - a.1)^2 + (b.2 - a.2)^2) ≤
          ((c'.1 - a'.1) * (b'.2 - a'.2) - (c'.2 - a'.2) * (b'.1 - a'.1))^2 /
              ((b'.1 - a'.1)^2 + (b'.2 - a'.2)^2)) →
        False  := by
  intro Q hQ x hx y hy z hz hxyz a ha b hb c hc habc hmin
  have h_smaller :=
    exists_smaller_perp_triple Q hQ x hx y hy z hz hxyz a ha b hb c hc habc
  obtain ⟨a', ha', b', hb', c', hc', hnc, hlt⟩ := h_smaller
  have hge := hmin a' ha' b' hb' c' hc' hnc
  linarith

end Problems.sylvester_gallai
