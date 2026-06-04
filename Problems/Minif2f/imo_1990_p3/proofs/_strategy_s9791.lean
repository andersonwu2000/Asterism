import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_three_given_no_seven
import Problems.Minif2f.imo_1990_p3.proofs.L_seven_not_dvd_n_of_sq

namespace Problems.Minif2f.imo_1990_p3

-- Two-step split isolating 7 as the unique "bad" prime ≥ 5: (A)
-- `seven_not_dvd_n_of_sq` shows 7 ∤ n via 2ⁿ mod 7 cycling {1,2,4} (never -1),
-- using only the n² ∣ 2ⁿ+1 hypothesis (parent's 3∣n + ¬9∣n unused, so strictly
-- simpler scope). (B) `eq_three_given_no_seven` strengthens the parent with
-- the extra hypothesis ¬(7∣n) — the standard proof's minFac(n/3) order-of-2
-- argument gives p ∈ {3,7}, and ¬(7∣n) collapses the case split that killed
-- dead strategy s9590's `no_prime_ge_five_dvd` (which had to handle the
-- gcd(n,p-1)=3 case generically). Combiner trivially chains.
theorem s9791 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) → n = 3  := by
  intro n hn hdvd h3 h9
  have h_seven := seven_not_dvd_n_of_sq n hn hdvd
  exact eq_three_given_no_seven n hn hdvd h3 h9 h_seven

end Problems.Minif2f.imo_1990_p3
