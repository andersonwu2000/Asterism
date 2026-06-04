import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Image has 48 elements (a ∈ [3,8], b ∈ [1,4], d ∈ [0,1]); for each
-- n = 2^a·3^b·5^3·7^d we have lcm(5!,n) = n and 5·gcd(10!,n) = n. Direct decide.
theorem s9716 : ∀ n : ℕ, n ∈ ((Finset.Icc 3 8 ×ˢ Finset.Icc 1 4 ×ˢ Finset.Icc 0 1).image
      (fun p : ℕ × ℕ × ℕ => 2^p.1 * 3^p.2.1 * 5^3 * 7^p.2.2)) →
        Nat.lcm 5! n = 5 * Nat.gcd 10! n := by decide

end Problems.Minif2f.amc12a_2020_p21

