import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- nonzero_of_lcm_gcd_eq: n=0 makes lcm 5! 0 = 0 but 5 * gcd 10! 0 = 5*10! ≠ 0
theorem nonzero_of_lcm_gcd_eq :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n ≠ 0 := by
  intro n ⟨_, hlcm⟩ hn
  subst hn
  simp [Nat.lcm_zero_right, Nat.gcd_zero_right, Nat.factorial] at hlcm

end Problems.Minif2f.amc12a_2020_p21
