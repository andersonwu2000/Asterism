import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_three_of_no_large_prime_2
import Problems.Minif2f.imo_1990_p3.proofs.L_no_prime_ge_five_dvd_m_given_no_seven

namespace Problems.Minif2f.imo_1990_p3

-- Apply already-proved `eq_three_of_no_large_prime_2` (m=3 from 3∣m, ¬9∣m,
-- and no prime ≥5 dividing m). Sub-goal: derive `∀ p, Prime p → 5 ≤ p → ¬p ∣ m`
-- from `¬ 7 ∣ m` (the gcd/ord-of-2 argument collapses to p=7).
theorem s9847 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) → m = 3  := by
  intro m hm hdvd h3 h9 h7
  have h_no_large_prime :
      ∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ m :=
    no_prime_ge_five_dvd_m_given_no_seven m hm hdvd h3 h9 h7
  exact eq_three_of_no_large_prime_2 m hm hdvd h3 h9 h_no_large_prime

end Problems.Minif2f.imo_1990_p3
