import Mathlib
namespace Problems.Minif2f.imo_1977_p5

-- r_eq_41: AM-QM bound gives a+b ≤ 2q+1, so r ≤ 2q; combined with q²+r=1977
-- this forces q²+2q ≥ 1977 and q² ≤ 1977, which pins q=44 and r=41.
theorem r_eq_41 :
    ∀ (a b q r : ℕ) (h₀ : r < a + b) (h₁ : a ^ 2 + b ^ 2 = (a + b) * q + r)
    (h₂ : q ^ 2 + r = 1977), r = 41 := by
  intro a b q r h₀ h₁ h₂
  have hq_sq_le : q ^ 2 ≤ 1977 := by omega
  have h2ab : 2 * (a ^ 2 + b ^ 2) ≥ (a + b) ^ 2 := by
    nlinarith [sq_nonneg ((a : ℤ) - b)]
  have hab_le : (a + b) ^ 2 ≤ 2 * ((a + b) * q + r) := by linarith [h₁ ▸ h2ab]
  have hab_bound : a + b ≤ 2 * q + 1 := by nlinarith
  have hr_le : r ≤ 2 * q := by omega
  have hq_ge : q ^ 2 + 2 * q ≥ 1977 := by linarith
  have hq_le_44 : q ≤ 44 := by
    by_contra h
    push Not at h
    have hq45 : 45 ≤ q := by omega
    have := Nat.mul_le_mul hq45 hq45
    nlinarith
  have hq_ge_44 : q ≥ 44 := by
    by_contra h
    push Not at h
    have hq43 : q ≤ 43 := by omega
    have hq2 : q + 2 ≤ 45 := by omega
    have hmul := Nat.mul_le_mul hq43 hq2
    have heq : q * (q + 2) = q ^ 2 + 2 * q := by ring
    linarith
  have hq_eq : q = 44 := by omega
  subst hq_eq
  omega

end Problems.Minif2f.imo_1977_p5
