import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_three_of_no_large_prime_2
import Problems.Minif2f.imo_1990_p3.proofs.L_no_prime_ge_five_dvd_given_no_seven

namespace Problems.Minif2f.imo_1990_p3

-- Reduce to: no prime ≥ 5 divides m. With ¬(7∣m) added to parent's hypotheses,
-- the gcd(n, p-1) order-of-2 case split that killed dead s9590 collapses (only
-- p=7 was the bad case). Then chain with the already-proved
-- `eq_three_of_no_large_prime_2`.
theorem s9810 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) → m = 3  := by
  intro m hm hdvd h3 h9 h7
  have h_no_large_prime := no_prime_ge_five_dvd_given_no_seven m hm hdvd h3 h9 h7
  exact eq_three_of_no_large_prime_2 m hm hdvd h3 h9 h_no_large_prime
end Problems.Minif2f.imo_1990_p3
