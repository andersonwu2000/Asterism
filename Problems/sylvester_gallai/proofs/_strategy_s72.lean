import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s72_sub_1
import Problems.sylvester_gallai.proofs.L_s72_sub_2

namespace Problems.sylvester_gallai

theorem s72 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    1 / 2 < t →
    t < 1 →
    (c.1 - a.1) ^ 2 + (c.2 - a.2) ^ 2 < (p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2
    ∨ (c.1 - b.1) ^ 2 + (c.2 - b.2) ^ 2 < (p.1 - b.1) ^ 2 + (p.2 - b.2) ^ 2  := by
  intro p a b c t hcross hL hc1 hc2 ht1 ht2
  by_contra hboth
  simp only [not_or, not_lt] at hboth
  obtain ⟨h1, h2⟩ := hboth
  have hD : (p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1) ≠ 0 :=
    fun h => hcross (by linear_combination -h)
  -- c parametric squared distances
  have hca : (c.1 - a.1) ^ 2 + (c.2 - a.2) ^ 2 =
      t ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) := by rw [hc1, hc2]; ring
  have hcb : (c.1 - b.1) ^ 2 + (c.2 - b.2) ^ 2 =
      (t - 1) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) := by rw [hc1, hc2]; ring
  -- p-distance bounds (linear steps)
  have hpa : (p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2 ≤
      t ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) := by linarith
  have hpb : (p.1 - b.1) ^ 2 + (p.2 - b.2) ^ 2 ≤
      (t - 1) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) := by linarith
  -- Lagrange identities (ring)
  have hlag_a : ((p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2) *
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
      ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) ^ 2 +
      ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1)) ^ 2 := by ring
  have hlag_b : ((p.1 - b.1) ^ 2 + (p.2 - b.2) ^ 2) *
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
      ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
        ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 +
      ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1)) ^ 2 := by ring
  -- multiply p-bounds by L; make the ring identity t²·L·L = t²·L² explicit
  have hmul_a := mul_le_mul_of_nonneg_right hpa (le_of_lt hL)
  have hring_a : t ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) *
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
      t ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := by ring
  have hmul_b := mul_le_mul_of_nonneg_right hpb (le_of_lt hL)
  have hring_b : (t - 1) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) *
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
      (t - 1) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := by ring
  -- s72_sub_2 preconditions: all linarith from the ring equalities above
  have hpre1 : ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) ^ 2 +
      ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1)) ^ 2 ≤
      t ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := by
    linarith [hlag_a, hmul_a, hring_a]
  have hring_c : (1 - t) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 =
      (t - 1) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := by ring
  have hpre2 : ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
        ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 +
      ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1)) ^ 2 ≤
      (1 - t) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := by
    linarith [hlag_b, hmul_b, hring_b, hring_c]
  exact s72_sub_2
    ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1))
    ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2))
    ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)
    t hD hL ht1 ht2 hpre1 hpre2

end Problems.sylvester_gallai
