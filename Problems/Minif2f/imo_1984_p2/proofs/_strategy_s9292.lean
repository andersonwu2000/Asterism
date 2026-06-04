import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs
import Problems.Minif2f.imo_1984_p2.proofs.L_bound_from_div
import Problems.Minif2f.imo_1984_p2.proofs.L_seven_cube_div_quadratic

namespace Problems.Minif2f.imo_1984_p2

-- Two-step reduction via the identity
--   (a+b)^7 - a^7 - b^7 = 7·a·b·(a+b)·(a^2 + a·b + b^2)^2.
-- (1) seven_cube_div_quadratic: from 7^7 ∣ … and the three non-divisibilities,
--     cancel the prime factors carried by 7·a·b·(a+b) and conclude 7^3 ∣ a^2 + a·b + b^2.
-- (2) bound_from_div: from 7^3 = 343 ∣ a^2 + a·b + b^2 plus positivity, enumerate
--     the finitely many small candidate values of a+b ≤ 18 to rule them out.
theorem s9292 : ∀ (a b : ℤ) (h₀ : 0 < a ∧ 0 < b) (h₁ : ¬7 ∣ a) (h₂ : ¬7 ∣ b)
    (h₃ : ¬7 ∣ a + b) (h₄ : 7 ^ 7 ∣ (a + b) ^ 7 - a ^ 7 - b ^ 7), 19 ≤ a + b := by
  intro a b h₀ h₁ h₂ h₃ h₄
  have h_div3 := seven_cube_div_quadratic a b h₁ h₂ h₃ h₄
  exact bound_from_div a b h₀.1 h₀.2 h₁ h₂ h₃ h_div3

end Problems.Minif2f.imo_1984_p2
