import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- three_dvd_quad: dvd/nlinarith — if 3 ∣ a+1 then 3 ∣ a²-a+1, via zify + witness 3k²-3k+1
-- Key: a = 3k-1 forces a²-a+1 = 9k²-9k+3 = 3(3k²-3k+1); zify lifts ℕ sub safely after
-- establishing a ≥ 2 (so a ≤ a²) from the divisibility hypothesis.
theorem three_dvd_quad : ∀ (a : ℕ), 3 ∣ a + 1 → 3 ∣ a^2 - a + 1 := by
  intro a h
  have ha : 2 ≤ a := by
    have := Nat.le_of_dvd (by omega) h; omega
  have hle : a ≤ a ^ 2 := by nlinarith
  obtain ⟨k, hk⟩ := h
  zify [hle] at *
  exact ⟨3 * k ^ 2 - 3 * k + 1, by nlinarith [sq_nonneg k]⟩

end Problems.Minif2f.imo_1990_p3
