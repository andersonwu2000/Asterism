import Mathlib
import Problems.Minif2f.mathd_numbertheory_303.Defs

namespace Problems.Minif2f.mathd_numbertheory_303

-- dvd_91_ge_2_in_set: enumerate divisors of 91 via Nat.divisors decide + omega
-- Compute Nat.divisors 91 = {1, 7, 13, 91} by decide, then membership + omega close the goal.
theorem dvd_91_ge_2_in_set :
    ∀ n : ℕ, n ∣ 91 → 2 ≤ n → (n = 7 ∨ n = 13 ∨ n = 91) := by
  intro n hn hge
  have hle : n ≤ 91 := Nat.le_of_dvd (by norm_num) hn
  have hmem : n ∈ Nat.divisors 91 := Nat.mem_divisors.mpr ⟨hn, by norm_num⟩
  have hdivs : Nat.divisors 91 = {1, 7, 13, 91} := by decide
  rw [hdivs] at hmem
  simp [Finset.mem_insert] at hmem
  omega

end Problems.Minif2f.mathd_numbertheory_303
