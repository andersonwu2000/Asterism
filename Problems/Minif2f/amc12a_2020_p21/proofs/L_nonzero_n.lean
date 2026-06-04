import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- nonzero_n: n = 0 makes lcm(5!,0)=0 but 5*gcd(10!,0)=5*10! ≠ 0; norm_num closes.
theorem nonzero_n :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n ≠ 0 := by
  intro n ⟨h5, hlcm⟩ hn
  subst hn
  norm_num at hlcm

end Problems.Minif2f.amc12a_2020_p21
