import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- nine_not_dvd_quad: 3∣a+1 implies 9∤a²-a+1 (write a+1=3k; then a²-a+1=3(3k²-3k+1)≡3 mod 9)
theorem nine_not_dvd_quad : ∀ (a : ℕ), 1 ≤ a → 3 ∣ a + 1 → ¬ 9 ∣ a^2 - a + 1 := by
  intro a ha ⟨k, hk⟩ ⟨m, hm⟩
  have hle : a ≤ a^2 := by nlinarith [sq_nonneg a]
  zify [hle] at hk hm
  have h2 : (a:ℤ)^2 + 2*(a:ℤ) + 1 = 9*(k:ℤ)^2 := by
    linear_combination ((a:ℤ) + 1 + 3*(k:ℤ)) * hk
  have h3 : 9*(k:ℤ)^2 - 9*(k:ℤ) - 9*(m:ℤ) + 3 = 0 := by linarith [h2, hm, hk]
  set p : ℤ := (k:ℤ)^2 - (k:ℤ) with hp
  have h4 : 9 * p - 9 * (m:ℤ) + 3 = 0 := by linarith [h3, hp]
  omega

end Problems.Minif2f.imo_1990_p3
