import Mathlib
namespace Problems.Minif2f.numbertheory_sqmod3in01d

-- sq_mod3_of_mod3_eq_one: factor a²-1=(a-1)(a+1), use 3∣(a-1) to get 3∣(a²-1), then omega
theorem sq_mod3_of_mod3_eq_one (a : ℤ) (h : a % 3 = 1) : a ^ 2 % 3 = 1 := by
  have h1 : (3 : ℤ) ∣ a ^ 2 - 1 := by
    have h2 : (3 : ℤ) ∣ a - 1 := by omega
    obtain ⟨k, hk⟩ := h2
    exact ⟨k * (a + 1), by linear_combination (a + 1) * hk⟩
  omega

end Problems.Minif2f.numbertheory_sqmod3in01d
