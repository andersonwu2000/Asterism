import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- three_dvd_quad_2: if 3 ∣ a+1 then 3 ∣ a²-a+1, via zify + witness 3k²-3k+1
-- Obtain k with a+1=3k, lift to ℤ, supply explicit dvd witness, close with nlinarith.
theorem three_dvd_quad_2 : ∀ (a : ℕ), 3 ∣ a + 1 → 3 ∣ a^2 - a + 1 := by
  intro a h
  obtain ⟨k, hk⟩ := h
  have hk1 : 1 ≤ k := by omega
  have hle : a ≤ a ^ 2 := by nlinarith
  zify [hle] at *
  exact ⟨3 * (k : ℤ) ^ 2 - 3 * k + 1, by nlinarith [sq_nonneg (k : ℤ)]⟩

end Problems.Minif2f.imo_1990_p3
