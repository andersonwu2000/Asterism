import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_minimizer_contradicts
import Problems.sylvester_gallai.proofs.L_kelly_minimizer_exists

namespace Problems.sylvester_gallai

-- Kelly's minimisation strategy in two stages: first extract a non-collinear
-- triple (a,b,c) ∈ Q³ minimising the squared perpendicular distance from c to
-- the line through a and b; then show no such minimiser is compatible with
-- hypothesis hQ (foot-of-perpendicular yields a strictly closer triple).
-- Each sub-goal is strictly simpler: `kelly_minimizer_exists` is pure finite
-- minimisation (hQ is unused in essence), `kelly_minimizer_contradicts` is the
-- geometric foot argument with the minimum already provided as hypothesis.
theorem s377 :
    ∀ (Q : Finset (ℝ × ℝ)),
      (∀ p ∈ Q, ∀ q ∈ Q, p ≠ q → ∃ r ∈ Q, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ x ∈ Q, ∀ y ∈ Q, ∀ z ∈ Q, ¬ Collinear x y z → False  := by
  intro Q hQ x hxQ y hyQ z hzQ hnxyz
  obtain ⟨a, ha, b, hb, c, hc, hnabc, hmin⟩ :=
    kelly_minimizer_exists Q hQ x hxQ y hyQ z hzQ hnxyz
  exact kelly_minimizer_contradicts Q hQ x hxQ y hyQ z hzQ hnxyz a ha b hb c hc hnabc hmin

end Problems.sylvester_gallai
