import Mathlib
import Problems.Minif2f.mathd_numbertheory_35.Defs

namespace Problems.Minif2f.mathd_numbertheory_35

-- Nat.sqrt 196 = 14, so S = Nat.divisors 14 = {1,2,7,14}; sum = 24 by decide.
theorem s723 : ∀ (S : Finset ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ n ∣ Nat.sqrt 196), (∑ k ∈ S, k) = 24  := by
  intro S h₀
  have hsqrt : Nat.sqrt 196 = 14 := by
    rw [show (196 : ℕ) = 14 * 14 from rfl, Nat.sqrt_eq]
  have hS : S = Nat.divisors 14 := by
    ext n
    rw [h₀, hsqrt, Nat.mem_divisors]
    simp
  rw [hS]
  decide
end Problems.Minif2f.mathd_numbertheory_35
