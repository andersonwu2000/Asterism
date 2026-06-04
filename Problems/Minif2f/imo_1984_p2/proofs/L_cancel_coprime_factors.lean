import Mathlib
namespace Problems.Minif2f.imo_1984_p2

-- cancel_coprime_factors: peel the explicit factor of 7 via mul_dvd_mul_iff_left,
-- then cancel x·y·(x+y) via Prime.coprime_iff_not_dvd + IsCoprime.pow_left,
-- concluding 7^6 ∣ Q^2 by IsCoprime.dvd_of_dvd_mul_left.
theorem cancel_coprime_factors : ∀ (x y : ℤ), ¬7 ∣ x → ¬7 ∣ y → ¬7 ∣ x + y →
    (7:ℤ) ^ 7 ∣ 7 * x * y * (x + y) * (x ^ 2 + x * y + y ^ 2) ^ 2 →
    (7:ℤ) ^ 6 ∣ (x ^ 2 + x * y + y ^ 2) ^ 2 := by
  intro x y hx hy hxy hdvd
  have h7ne : (7:ℤ) ≠ 0 := by norm_num
  have hp : Prime (7:ℤ) := by norm_num
  have h1 : (7:ℤ)^6 ∣ x * y * (x + y) * (x ^ 2 + x * y + y ^ 2) ^ 2 := by
    have key : (7:ℤ) * (7:ℤ)^6 ∣ 7 * (x * y * (x + y) * (x ^ 2 + x * y + y ^ 2) ^ 2) := by
      convert hdvd using 1; ring
    exact (mul_dvd_mul_iff_left h7ne).mp key
  have hcx : IsCoprime (7:ℤ) x := (hp.coprime_iff_not_dvd).mpr hx
  have hcy : IsCoprime (7:ℤ) y := (hp.coprime_iff_not_dvd).mpr hy
  have hcxy : IsCoprime (7:ℤ) (x + y) := (hp.coprime_iff_not_dvd).mpr hxy
  have hc : IsCoprime ((7:ℤ)^6) (x * y * (x + y)) := by
    apply IsCoprime.pow_left
    exact (hcx.mul_right hcy).mul_right hcxy
  exact hc.dvd_of_dvd_mul_left h1

end Problems.Minif2f.imo_1984_p2
