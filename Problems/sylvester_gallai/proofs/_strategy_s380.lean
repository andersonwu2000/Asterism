import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_descent_step

namespace Problems.sylvester_gallai

-- Apply collinearity-closure to (a,b) (distinct since ¬Collinear a b c)
-- to get a third point r ∈ Q on line(a,b); then Kelly's descent step on
-- the configuration (a,b,r,c) produces the smaller triple.
-- Sub-goal `kelly_descent_step` is strictly simpler: it adds the third
-- collinear point r as a hypothesis, removing the need to invoke hQ
-- and packaging the geometric foot-of-perpendicular argument with
-- direct access to the three collinear witnesses on line(a,b).
theorem s380 :
    ∀ (Q : Finset (ℝ × ℝ)),
      (∀ p ∈ Q, ∀ q ∈ Q, p ≠ q → ∃ r ∈ Q, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ x ∈ Q, ∀ y ∈ Q, ∀ z ∈ Q, ¬ Collinear x y z →
      ∀ a ∈ Q, ∀ b ∈ Q, ∀ c ∈ Q, ¬ Collinear a b c →
      ∃ a' ∈ Q, ∃ b' ∈ Q, ∃ c' ∈ Q, ¬ Collinear a' b' c' ∧
        ((c'.1 - a'.1) * (b'.2 - a'.2) - (c'.2 - a'.2) * (b'.1 - a'.1))^2 /
            ((b'.1 - a'.1)^2 + (b'.2 - a'.2)^2) <
        ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 /
            ((b.1 - a.1)^2 + (b.2 - a.2)^2)  := by
  intro Q hQ x hx y hy z hz hxyz a ha b hb c hc habc
  have hab : a ≠ b := by
    intro h
    apply habc
    subst h
    unfold Collinear
    ring
  obtain ⟨r, hr, hcoll, hrne_a, hrne_b⟩ := hQ a ha b hb hab
  exact kelly_descent_step Q hQ x hx y hy z hz hxyz a ha b hb c hc habc r hr hcoll hrne_a hrne_b

end Problems.sylvester_gallai
