import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_collinear_iff_param
import Problems.sylvester_gallai.proofs.L_kelly_smaller_with_param


namespace Problems.sylvester_gallai

-- Unpack `Collinear p q s` into the parametric form `s = p + t_s*(q - p)` via
-- `collinear_iff_param`; translate `s ≠ p`, `s ≠ q` into `t_s ≠ 0`, `t_s ≠ 1`.
-- The single sub-goal `kelly_smaller_with_param` then handles Kelly's geometric
-- construction (foot of perpendicular, pigeonhole via `three_reals_same_side`,
-- and ratio comparison via `perp_numerator_sq_param_factor`) in explicit
-- parametric form — strictly simpler than the parent because the third
-- collinear point is now a concrete affine combination of `p` and `q`.
theorem s10213 : ∀ (P : Finset (ℝ × ℝ)) (p : ℝ × ℝ), p ∈ P →
    ∀ (q : ℝ × ℝ), q ∈ P → ∀ (r : ℝ × ℝ), r ∈ P → p ≠ q → ¬ Collinear p q r →
    (∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
      ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2
          / ((q.1 - p.1)^2 + (q.2 - p.2)^2) ≤
      ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1))^2
          / ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2)) →
    ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
    ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
      ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1))^2
          / ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2) <
      ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2
          / ((q.1 - p.1)^2 + (q.2 - p.2)^2) := by
  intro P p hpP q hqP r hrP hpq hncol hmin s hsP hcols hsp hsq
  obtain ⟨t_s, hs1, hs2⟩ := (collinear_iff_param p q s hpq).mp hcols
  have ht_s_0 : t_s ≠ 0 := by
    intro ht
    apply hsp
    ext
    · rw [hs1, ht]; ring
    · rw [hs2, ht]; ring
  have ht_s_1 : t_s ≠ 1 := by
    intro ht
    apply hsq
    ext
    · rw [hs1, ht]; ring
    · rw [hs2, ht]; ring
  have h_kelly := kelly_smaller_with_param P p hpP q hqP r hrP hpq hncol hmin
    s hsP t_s hs1 hs2 ht_s_0 ht_s_1
  exact h_kelly

end Problems.sylvester_gallai
