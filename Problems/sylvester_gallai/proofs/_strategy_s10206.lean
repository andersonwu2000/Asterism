import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_min_perp_over_valid_triples
import Problems.sylvester_gallai.proofs.L_valid_triple_exists

namespace Problems.sylvester_gallai

-- Decompose into (1) existence of any valid triple from non-collinearity,
-- (2) extraction of the minimum over the (non-empty, finite) set of valid triples.
theorem s10206 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r ∧
      ∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
        ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2
            / ((q.1 - p.1)^2 + (q.2 - p.2)^2) ≤
        ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1))^2
            / ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2)  := by
  intro P hexists
  have h_valid := valid_triple_exists P hexists
  exact min_perp_over_valid_triples P h_valid

end Problems.sylvester_gallai
