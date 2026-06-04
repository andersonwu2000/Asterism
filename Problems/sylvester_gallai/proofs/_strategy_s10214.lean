import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_smaller_two_same_side

namespace Problems.sylvester_gallai

-- Inline 3-real pigeonhole on the parameters {0, 1, t_s} (for p, q, s along
-- line pq) against the foot-of-perpendicular parameter t_f, yielding three
-- cases of a same-side pair. In each case dispatch to the abstract single
-- sub-lemma `kelly_smaller_two_same_side`, which encapsulates Kelly's
-- closer-of-two construction + ratio comparison via
-- `perp_numerator_sq_param_factor`. Strictly simpler than the parent: the
-- sub-lemma's pair (a, b) is generic, so the proof handles one symmetric case
-- rather than three intertwined ones.
theorem s10214 :
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
    ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
      ((p'.1 - r'.1) * (q'.2 - r'.2) - (p'.2 - r'.2) * (q'.1 - r'.1))^2
          / ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2) <
      ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2
          / ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P p hpP q hqP r hrP hpq hncol hmin s hsP t_s hs1 hs2 hts0 hts1
  set t_f : ℝ := ((r.1 - p.1) * (q.1 - p.1) + (r.2 - p.2) * (q.2 - p.2))
      / ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2) with ht_f_def
  have h_split : ((0:ℝ) - t_f) * ((1:ℝ) - t_f) ≥ 0
        ∨ ((0:ℝ) - t_f) * (t_s - t_f) ≥ 0
        ∨ ((1:ℝ) - t_f) * (t_s - t_f) ≥ 0 := by
    rcases le_or_gt t_f 0 with h1 | h1
    · left; nlinarith
    · rcases le_or_gt 1 t_f with h2 | h2
      · left; nlinarith
      · rcases le_total t_s t_f with h3 | h3
        · right; left; nlinarith
        · right; right; nlinarith
  have h_kelly := kelly_smaller_two_same_side P p hpP q hqP r hrP hpq hncol hmin
    s hsP t_s hs1 hs2 hts0 hts1
  rcases h_split with hpq_side | hps_side | hqs_side
  · have hp1 : p.1 = p.1 + (0:ℝ) * (q.1 - p.1) := by ring
    have hp2 : p.2 = p.2 + (0:ℝ) * (q.2 - p.2) := by ring
    have hq1 : q.1 = p.1 + (1:ℝ) * (q.1 - p.1) := by ring
    have hq2 : q.2 = p.2 + (1:ℝ) * (q.2 - p.2) := by ring
    exact h_kelly p hpP q hqP 0 1 t_f hp1 hp2 hq1 hq2 (by norm_num) ht_f_def hpq_side
  · have hp1 : p.1 = p.1 + (0:ℝ) * (q.1 - p.1) := by ring
    have hp2 : p.2 = p.2 + (0:ℝ) * (q.2 - p.2) := by ring
    exact h_kelly p hpP s hsP 0 t_s t_f hp1 hp2 hs1 hs2 (Ne.symm hts0) ht_f_def hps_side
  · have hq1 : q.1 = p.1 + (1:ℝ) * (q.1 - p.1) := by ring
    have hq2 : q.2 = p.2 + (1:ℝ) * (q.2 - p.2) := by ring
    exact h_kelly q hqP s hsP 1 t_s t_f hq1 hq2 hs1 hs2 (Ne.symm hts1) ht_f_def hqs_side

end Problems.sylvester_gallai
