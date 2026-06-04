import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_b_ne_r_when_on_param_line
import Problems.sylvester_gallai.proofs.L_not_collinear_b_r_a_param
import Problems.sylvester_gallai.proofs.L_perpdist_strict_smaller_for_closer_a

namespace Problems.sylvester_gallai

-- Construct the witness `(p', q', r') = (b, r, a)`: new line through `b, r`
-- with `a` as off-line point. Three sub-claims:
-- (1) `b ≠ r` — `b` is on line(p,q) (param `t_b`), `r` is off (`¬ Collinear p q r`).
-- (2) `¬ Collinear b r a` — `a, b` are distinct points on line(p,q) (`t_a ≠ t_b`),
--     `r` is off, so `a` is not on line(b,r).
-- (3) Strict ratio inequality. Algebraic identities: new numerator factors as
--     `(t_b - t_a)^2 * OldNum`; new denominator `(r-b).1² + (r-b).2²` expands to
--     `OldNum/|q-p|² + (t_b - t_f)² · |q-p|²` using the foot-of-perpendicular
--     formula for `t_f`. The same-side + ordered hypotheses give
--     `(t_b - t_a)² ≤ (t_b - t_f)²`, and `OldNum > 0` (from `¬ Collinear p q r`)
--     supplies the strict gap.
theorem s10216 :
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
      (t_a - t_f)^2 ≤ (t_b - t_f)^2 →
    ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
      ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1)) ^ 2
          / ((q'.1 - p'.1) ^ 2 + (q'.2 - p'.2) ^ 2) <
      ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) ^ 2
          / ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2)  := by
  intro P p hpP q hqP r hrP hpq hncol hmin s hsP t_s hs1 hs2 hts0 hts1
        a haP b hbP t_a t_b t_f ha1 ha2 hb1 hb2 hab ht_f h_same h_close
  have h1 := b_ne_r_when_on_param_line p q r b t_b hpq hncol hb1 hb2
  have h2 := not_collinear_b_r_a_param p q r a b t_a t_b hpq hncol
              ha1 ha2 hb1 hb2 hab
  have h3 := perpdist_strict_smaller_for_closer_a p q r a b t_a t_b t_f
              hpq hncol ha1 ha2 hb1 hb2 hab ht_f h_same h_close
  exact ⟨b, hbP, r, hrP, a, haP, h1, h2, h3⟩

end Problems.sylvester_gallai
