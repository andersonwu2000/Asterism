import Mathlib
import Problems.Minif2f.amc12b_2002_p3.Defs

namespace Problems.Minif2f.amc12b_2002_p3

-- prime_expr_unique_three: n^2+2-3n prime and 0<n implies n=3,
-- proved by casework on n<4 (n=1,2 give 0 which is not prime, n=3 gives 2 which is prime),
-- then for n≥4 factoring as (n-1)*(n-2) with both factors ≥2 yields contradiction.
theorem prime_expr_unique_three :
    ∀ n : ℕ, 0 < n → Nat.Prime (n ^ 2 + 2 - 3 * n) → n = 3 := by
  intro n hn hprime
  rcases Nat.lt_or_ge n 4 with h | h
  · have : n = 1 ∨ n = 2 ∨ n = 3 := by omega
    rcases this with rfl | rfl | rfl
    · norm_num at hprime
    · norm_num at hprime
    · rfl
  · have hle : 3 * n ≤ n ^ 2 + 2 := by nlinarith
    have hfactor : n ^ 2 + 2 - 3 * n = (n - 1) * (n - 2) := by
      zify [show 1 ≤ n from by omega, show 2 ≤ n from by omega, hle]; ring
    rw [hfactor] at hprime
    have hpos : 0 < n - 2 := by omega
    rcases hprime.eq_one_or_self_of_dvd (n - 2) (dvd_mul_left (n - 2) (n - 1)) with h1 | h2
    · omega
    · have hge : 2 ≤ n - 1 := by omega
      have hmul : 2 * (n - 2) ≤ (n - 1) * (n - 2) := Nat.mul_le_mul_right _ hge
      linarith [h2.symm]

end Problems.Minif2f.amc12b_2002_p3
