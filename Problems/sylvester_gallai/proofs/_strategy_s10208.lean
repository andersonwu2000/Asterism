import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_min_arg_valid_triple

namespace Problems.sylvester_gallai

-- Generalise the perpendicular-distance function to an abstract `f`; the
-- existence of an arg-minimum over valid triples is independent of the
-- specific function form. Sub-goal `min_arg_valid_triple` does the
-- Finset.exists_min_image extraction; combinator instantiates `f` with
-- the perpendicular-distance squared.
theorem s10208 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r) →
    ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r ∧
      ∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
        ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2
            / ((q.1 - p.1)^2 + (q.2 - p.2)^2) ≤
        ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1))^2
            / ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2)  := by
  intro P hexists
  exact min_arg_valid_triple P
    (fun p q r => ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2
        / ((q.1 - p.1)^2 + (q.2 - p.2)^2)) hexists

end Problems.sylvester_gallai
