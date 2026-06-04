import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs

namespace Problems.Minif2f.amc12a_2008_p15

-- k_ge_4: 4 ≤ 2008^2 + 2^2008 via norm_num on the small factor and Nat.le_add_right
theorem k_ge_4 : ∀ (k : ℕ) (h₀ : k = 2008 ^ 2 + 2 ^ 2008), 4 ≤ k := by
  intro k h₀
  have h1 : 4 ≤ 2008 ^ 2 := by norm_num
  have h2 : 2008 ^ 2 ≤ 2008 ^ 2 + 2 ^ 2008 := Nat.le_add_right _ _
  omega

end Problems.Minif2f.amc12a_2008_p15
