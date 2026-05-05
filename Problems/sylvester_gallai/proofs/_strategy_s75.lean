import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s75_sub_1
import Problems.sylvester_gallai.proofs.L_s75_sub_2
import Problems.sylvester_gallai.proofs.L_s75_sub_3
import Problems.sylvester_gallai.proofs.L_s75_sub_4

namespace Problems.sylvester_gallai

theorem s75 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    1 / 2 < t →
    1 < t →
    (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 <
    (p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2 ∨
    (b.1 - c.1) ^ 2 + (b.2 - c.2) ^ 2 <
    (p.1 - c.1) ^ 2 + (p.2 - c.2) ^ 2  := by
  intro p a b c t hD hL hc1 hc2 _hca _hcb _ht1 ht2
  have hDne : (p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1) ≠ 0 :=
    sub_ne_zero.mpr hD
  have hD2pos : 0 < ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 :=
    sq_pos_of_ne_zero hDne
  have h_lag_a : ((p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2) *
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
      ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) ^ 2 +
      ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 :=
    s75_sub_1 p a b
  have h_lag_c : ((p.1 - c.1) ^ 2 + (p.2 - c.2) ^ 2) *
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
      ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
        t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 +
      ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 :=
    s75_sub_2 p a b c t hc1 hc2
  have h_bc : (b.1 - c.1) ^ 2 + (b.2 - c.2) ^ 2 =
      (1 - t) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) :=
    s75_sub_3 a b c t hc1 hc2
  have h_disj :
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 <
        ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) ^ 2 +
        ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 ∨
      (1 - t) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 <
        ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
          t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 +
        ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 :=
    s75_sub_4
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)
      ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2))
      (((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2)
      t hL hD2pos ht2
  rcases h_disj with h1 | h2
  · left
    apply lt_of_mul_lt_mul_right _ (le_of_lt hL)
    calc ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)
        = ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := by ring
      _ < ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) ^ 2 +
          ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 := h1
      _ = ((p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) :=
          h_lag_a.symm
  · right
    apply lt_of_mul_lt_mul_right _ (le_of_lt hL)
    have hbc_mul : ((b.1 - c.1) ^ 2 + (b.2 - c.2) ^ 2) *
        ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
        (1 - t) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := by
      rw [h_bc]; ring
    calc ((b.1 - c.1) ^ 2 + (b.2 - c.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)
        = (1 - t) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := hbc_mul
      _ < ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
            t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 +
          ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 := h2
      _ = ((p.1 - c.1) ^ 2 + (p.2 - c.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) :=
          h_lag_c.symm

end Problems.sylvester_gallai
