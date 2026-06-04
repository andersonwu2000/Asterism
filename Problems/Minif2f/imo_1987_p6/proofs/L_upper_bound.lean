import Mathlib
namespace Problems.Minif2f.imo_1987_p6

-- upper_bound: sqrt-floor size contradiction — r > 2i forces (2i+1)²≤r²≤i²+i+p,
-- giving 3i²+3i+1≤p, but ⌊√(p/3)⌋ < i implies p < 3i² (via Real.sq_sqrt), contradiction.
theorem upper_bound : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p →
    r ≤ 2 * i := by
  intro p hp hbase i hi hfloor ih r hr hdvd hrsq
  by_contra h
  push Not at h
  have hr_ge : 2 * i + 1 ≤ r := h
  have hsq_lb : (2 * i + 1) ^ 2 ≤ r ^ 2 := Nat.pow_le_pow_left hr_ge 2
  have h1 : 3 * i ^ 2 + 3 * i + 1 ≤ p := by nlinarith [hsq_lb, hrsq]
  have h2 : Real.sqrt ((p : ℝ) / 3) < (i : ℝ) := by
    have hnn : 0 ≤ Real.sqrt ((p : ℝ) / 3) := Real.sqrt_nonneg _
    exact_mod_cast (Nat.floor_lt hnn).mp hfloor
  have h3 : (p : ℝ) / 3 < (i : ℝ) ^ 2 := by
    have hs : 0 ≤ (p : ℝ) / 3 := by positivity
    nlinarith [Real.sq_sqrt hs, Real.sqrt_nonneg ((p : ℝ) / 3)]
  have h4 : p < 3 * i ^ 2 := by exact_mod_cast (by linarith : (p : ℝ) < 3 * (i : ℝ) ^ 2)
  omega

end Problems.Minif2f.imo_1987_p6
