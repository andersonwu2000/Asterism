import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_det_sq_pos_of_not_collinear
import Problems.sylvester_gallai.proofs.L_newnum_sq_factors
import Problems.sylvester_gallai.proofs.L_qp_sq_sum_pos_of_ne
import Problems.sylvester_gallai.proofs.L_rb_sq_decomp
import Problems.sylvester_gallai.proofs.L_tdiff_ba_le_bf_sq

namespace Problems.sylvester_gallai

-- Decomposition: reduce the strict ratio inequality to five sub-claims that
-- nlinarith can combine after clearing denominators.
--   (1) h_tdiff: same-side + |t_a-t_f| ≤ |t_b-t_f| forces |t_b-t_a| ≤ |t_b-t_f|.
--   (2) h_newnum: the new numerator factors as (t_b - t_a)^2 * OldNum^2.
--   (3) h_denom: |r-b|^2 * D = OldNum^2 + (t_b-t_f)^2 * D^2 (after subst t_f).
--   (4) h_oldsq_pos: OldNum^2 > 0 from hncol (the determinant is nonzero).
--   (5) h_dsq_pos:  D = |q-p|^2 > 0 from hpq.
-- Combining: |r-b|^2 > 0 from (3,4,5); clear denominators with div_lt_div_iff,
-- rewrite numerator by (2), then nlinarith using (1,3,4,5).
theorem s10217
    (p q r a b : ℝ × ℝ) (t_a t_b t_f : ℝ)
    (hpq : p ≠ q) (hncol : ¬ Collinear p q r)
    (ha1 : a.1 = p.1 + t_a * (q.1 - p.1))
    (ha2 : a.2 = p.2 + t_a * (q.2 - p.2))
    (hb1 : b.1 = p.1 + t_b * (q.1 - p.1))
    (hb2 : b.2 = p.2 + t_b * (q.2 - p.2))
    (hab : t_a ≠ t_b)
    (ht_f : t_f = ((r.1 - p.1) * (q.1 - p.1) + (r.2 - p.2) * (q.2 - p.2))
              / ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2))
    (h_same : (t_a - t_f) * (t_b - t_f) ≥ 0)
    (h_close : (t_a - t_f) ^ 2 ≤ (t_b - t_f) ^ 2) :
    ((b.1 - a.1) * (r.2 - a.2) - (b.2 - a.2) * (r.1 - a.1)) ^ 2
        / ((r.1 - b.1) ^ 2 + (r.2 - b.2) ^ 2) <
    ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) ^ 2
        / ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2)  := by
  have h_tdiff := tdiff_ba_le_bf_sq t_a t_b t_f h_same h_close
  have h_newnum := newnum_sq_factors p q r a b t_a t_b ha1 ha2 hb1 hb2
  have h_denom := rb_sq_decomp p q r b t_b t_f hpq hb1 hb2 ht_f
  have h_oldsq_pos := det_sq_pos_of_not_collinear p q r hncol
  have h_dsq_pos := qp_sq_sum_pos_of_ne p q hpq
  set OldSq := ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1))^2 with hOldSq
  set D := (q.1 - p.1)^2 + (q.2 - p.2)^2 with hD
  have h_keyD : (t_b - t_a)^2 * D^2 < OldSq + (t_b - t_f)^2 * D^2 := by
    have hmul := mul_le_mul_of_nonneg_right h_tdiff (sq_nonneg D)
    linarith [hmul, h_oldsq_pos]
  have h_rbsq_pos : 0 < (r.1 - b.1)^2 + (r.2 - b.2)^2 := by
    have h_rhs_pos : 0 < OldSq + (t_b - t_f)^2 * D^2 :=
      add_pos_of_pos_of_nonneg h_oldsq_pos
        (mul_nonneg (sq_nonneg _) (sq_nonneg _))
    have h_prod_pos :
        0 < ((r.1 - b.1)^2 + (r.2 - b.2)^2) * D := by
      rw [h_denom]; exact h_rhs_pos
    have h_branch : 0 < (r.1 - b.1)^2 + (r.2 - b.2)^2 ∧ 0 < D :=
      (mul_pos_iff.mp h_prod_pos).resolve_right
        (fun h => absurd h.2 (not_lt.mpr h_dsq_pos.le))
    exact h_branch.1
  rw [div_lt_div_iff₀ h_rbsq_pos h_dsq_pos, h_newnum]
  -- Goal: (t_b - t_a)^2 * OldSq * D < OldSq * |r-b|^2
  have h1 : (t_b - t_a)^2 * D^2 < ((r.1 - b.1)^2 + (r.2 - b.2)^2) * D := by
    rw [h_denom]; exact h_keyD
  -- Cancel one factor of D using positivity
  have h2 : (t_b - t_a)^2 * D < (r.1 - b.1)^2 + (r.2 - b.2)^2 := by
    have h1' : ((t_b - t_a)^2 * D) * D < ((r.1 - b.1)^2 + (r.2 - b.2)^2) * D := by
      have h_rw : (t_b - t_a)^2 * D^2 = ((t_b - t_a)^2 * D) * D := by ring
      linarith [h1, h_rw.symm]
    exact lt_of_mul_lt_mul_right h1' h_dsq_pos.le
  have h3 : OldSq * ((t_b - t_a)^2 * D) < OldSq * ((r.1 - b.1)^2 + (r.2 - b.2)^2) :=
    mul_lt_mul_of_pos_left h2 h_oldsq_pos
  linarith [h3]
end Problems.sylvester_gallai
