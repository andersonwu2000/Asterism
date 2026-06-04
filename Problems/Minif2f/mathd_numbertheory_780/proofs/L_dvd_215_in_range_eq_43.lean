import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_780

-- dvd_215_in_range_eq_43: 215 = 5 * 43; only divisor in [10, 99] is 43.
-- interval_cases enumerates all m in [10, 99]; omega closes each via the dvd hypothesis.
theorem dvd_215_in_range_eq_43 : ∀ (m : ℤ) (h₁ : 10 ≤ m ∧ m ≤ 99) (hd : m ∣ 215), m = 43 := by
  intro m ⟨hlo, hhi⟩ hdvd
  interval_cases m <;> omega

end Problems.Minif2f.mathd_numbertheory_780
