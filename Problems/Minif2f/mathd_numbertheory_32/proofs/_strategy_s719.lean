import Mathlib
import Problems.Minif2f.mathd_numbertheory_32.Defs

namespace Problems.Minif2f.mathd_numbertheory_32

-- Direct proof: S extensionally equals `Nat.divisors 36`, then `decide` evaluates the sum.
theorem s719 : ∀ (S : Finset ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ n ∣ 36), (∑ k ∈ S, k) = 91  := by
  intro S h₀
  have hS : S = Nat.divisors 36 := by
    ext n
    rw [h₀, Nat.mem_divisors]
    refine ⟨fun h => ⟨h, by norm_num⟩, fun h => h.1⟩
  rw [hS]
  decide

end Problems.Minif2f.mathd_numbertheory_32
