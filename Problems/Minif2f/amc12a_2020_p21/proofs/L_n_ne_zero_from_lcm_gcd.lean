import Mathlib
open Nat
namespace Problems.Minif2f.amc12a_2020_p21

-- n_ne_zero_from_lcm_gcd: when n=0, Nat.lcm 5! 0 = 0 contradicts 5 * Nat.gcd 10! 0 ≠ 0;
-- intro+subst n=0 then norm_num on concrete lcm/gcd values closes False
theorem n_ne_zero_from_lcm_gcd :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n ≠ 0 := by
  intro n ⟨_, hlcm⟩ hn
  subst hn
  norm_num at hlcm

end Problems.Minif2f.amc12a_2020_p21
