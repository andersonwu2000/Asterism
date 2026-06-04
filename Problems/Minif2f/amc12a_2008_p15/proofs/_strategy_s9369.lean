import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs

namespace Problems.Minif2f.amc12a_2008_p15

-- Direct proof: 2008^2 ≡ 4 (mod 10) by norm_num; 2^2008 ≡ 6 (mod 10) via
-- 4-cycle induction (2008 = 4*501 + 4); then Nat.add_mod closes the goal.
theorem s9369 : ∀ (k : ℕ) (h₀ : k = 2008 ^ 2 + 2 ^ 2008), k % 10 = 0  := by
  intro k h₀
  have h1 : 2008 ^ 2 % 10 = 4 := by norm_num
  have h2 : 2 ^ 2008 % 10 = 6 := by
    have cycle : ∀ n : ℕ, 2 ^ (4 * n + 4) % 10 = 6 := by
      intro n
      induction n with
      | zero => norm_num
      | succ n ih =>
        have heq : 4 * (n + 1) + 4 = 4 * n + 4 + 4 := by ring
        rw [heq, pow_add, Nat.mul_mod, ih]
        norm_num
    have h2008 : 2008 = 4 * 501 + 4 := by norm_num
    conv_lhs => rw [h2008]
    exact cycle 501
  have h3 : (2008 ^ 2 + 2 ^ 2008) % 10 = 0 := by
    have hadd : (2008 ^ 2 + 2 ^ 2008) % 10 = (2008 ^ 2 % 10 + 2 ^ 2008 % 10) % 10 :=
      Nat.add_mod _ _ _
    rw [hadd, h1, h2]
  omega

end Problems.Minif2f.amc12a_2008_p15
