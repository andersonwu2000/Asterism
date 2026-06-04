import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_smaller_two_same_side_ordered

namespace Problems.sylvester_gallai

-- WLOG on which of {a, b} is closer to the foot of perpendicular (parameter
-- t_f), by case-splitting on the comparison of squared parameter distances
-- to t_f. In each case dispatch to the asymmetric helper
-- `kelly_smaller_two_same_side_ordered`, which assumes `(t_a - t_f)^2 ≤
-- (t_b - t_f)^2` (a is the closer point) and constructs the new triple
-- (b, r, a) whose squared perpendicular distance is strictly less than the
-- original, via `perp_numerator_sq_param_factor` for the numerator factor
-- (t_b - t_a)^2 and the parameter-bound argument for the denominator.
-- Strictly simpler than the parent: the helper handles a single ordered
-- pair rather than an unordered same-side pair.
theorem s10215 :
    ∀ (P : Finset (ℝ × ℝ)) (p : ℝ × ℝ), p ∈ P →
    ∀ (q : ℝ × ℝ), q ∈ P → ∀ (r : ℝ × ℝ), r ∈ P → p ≠ q → ¬ Collinear p q r →
    (∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
      ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2
          / ((q.1 - p.1)^2 + (q.2 - p.2)^2) ≤
      ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1))^2
          / ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2)) →
    ∀ s ∈ P, ∀ t_s : ℝ,
      s.1 = p.1 + t_s * (q.1 - p.1) → s.2 = p.2 + t_s * (q.2 - p.2) →
      t_s ≠ 0 → t_s ≠ 1 →
    ∀ a ∈ P, ∀ b ∈ P, ∀ t_a t_b t_f : ℝ,
      a.1 = p.1 + t_a * (q.1 - p.1) → a.2 = p.2 + t_a * (q.2 - p.2) →
      b.1 = p.1 + t_b * (q.1 - p.1) → b.2 = p.2 + t_b * (q.2 - p.2) →
      t_a ≠ t_b →
      t_f = ((r.1 - p.1) * (q.1 - p.1) + (r.2 - p.2) * (q.2 - p.2))
              / ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2) →
      (t_a - t_f) * (t_b - t_f) ≥ 0 →
    ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
      ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1)) ^ 2
          / ((q'.1 - p'.1) ^ 2 + (q'.2 - p'.2) ^ 2) <
      ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) ^ 2
          / ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2)  := by
  intro P p hpP q hqP r hrP hpq hncol hmin s hsP t_s hs1 hs2 hts0 hts1
    a haP b hbP t_a t_b t_f ha1 ha2 hb1 hb2 hab ht_f h_same
  have h_helper := kelly_smaller_two_same_side_ordered
  rcases le_total ((t_a - t_f)^2) ((t_b - t_f)^2) with h_close | h_close
  · exact h_helper P p hpP q hqP r hrP hpq hncol hmin
      s hsP t_s hs1 hs2 hts0 hts1 a haP b hbP t_a t_b t_f
      ha1 ha2 hb1 hb2 hab ht_f h_same h_close
  · have h_same' : (t_b - t_f) * (t_a - t_f) ≥ 0 := by
      rw [mul_comm]; exact h_same
    exact h_helper P p hpP q hqP r hrP hpq hncol hmin
      s hsP t_s hs1 hs2 hts0 hts1 b hbP a haP t_b t_a t_f
      hb1 hb2 ha1 ha2 (Ne.symm hab) ht_f h_same' h_close

end Problems.sylvester_gallai
