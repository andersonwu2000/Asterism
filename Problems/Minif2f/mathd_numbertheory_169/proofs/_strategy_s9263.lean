import Mathlib
import Problems.Minif2f.mathd_numbertheory_169.Defs

open Nat

namespace Problems.Minif2f.mathd_numbertheory_169

-- Closed numerical fact: 20! = 2^18·3^8·5^4·…, 200000 = 2^6·5^5,
-- so gcd = 2^6·5^4 = 40000. `decide` reduces via the Euclidean
-- algorithm on Nat (no axioms; native_decide introduces rogue ax).
theorem s9263 : Nat.gcd 20! 200000 = 40000  := by decide

end Problems.Minif2f.mathd_numbertheory_169
