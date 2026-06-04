import Mathlib
namespace Problems.Minif2f.amc12b_2002_p11

-- b_eq_two: parity forces b = 2; odd+odd sum is even composite, contradicting h₂
-- Case split b = 2 vs b odd. If b odd: split a = 2 vs a odd.
-- a=2 branch: a-b = 0 in ℕ (b ≥ 3), so Nat.Prime 0 is absurd.
-- Both-odd branch: 2 ∣ a+b (omega) and a+b ≥ 6, so h₂.eq_one_or_self_of_dvd gives
-- 2 = 1 or 2 = a+b, both contradicted by omega.
theorem b_eq_two : ∀ (a b : ℕ) (h₀ : Nat.Prime a) (h₁ : Nat.Prime b)
    (h₂ : Nat.Prime (a + b)) (h₃ : Nat.Prime (a - b)), b = 2 := by
  intro a b h₀ h₁ h₂ h₃
  rcases Nat.Prime.eq_two_or_odd h₁ with rfl | hb_odd
  · rfl
  · have hb_ge : b ≥ 3 := by have := h₁.two_le; omega
    rcases Nat.Prime.eq_two_or_odd h₀ with rfl | ha_odd
    · have hab : (2 : ℕ) - b = 0 := by omega
      rw [hab] at h₃
      exact absurd h₃ Nat.not_prime_zero
    · have ha_ge : a ≥ 3 := by have := h₀.two_le; omega
      have heven : 2 ∣ a + b := by omega
      rcases h₂.eq_one_or_self_of_dvd 2 heven with h | h <;> omega

end Problems.Minif2f.amc12b_2002_p11
