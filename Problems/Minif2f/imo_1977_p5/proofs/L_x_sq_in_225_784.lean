import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs

namespace Problems.Minif2f.imo_1977_p5

-- x_sq_in_225_784: interval_cases x then interval_cases y then omega; 1009 is prime ≡ 1 (mod 4)
-- with unique sum-of-two-squares representation 15²+28²=1009, so the only integer pairs
-- (x,y) in the ±31 box satisfying x²+y²=1009 have x²∈{225,784}.
theorem x_sq_in_225_784 : ∀ (x y : ℤ), -31 ≤ x → x ≤ 31 → -31 ≤ y → y ≤ 31 →
    x ^ 2 + y ^ 2 = 1009 → x ^ 2 = 225 ∨ x ^ 2 = 784 := by
  intro x y hxl hxu hyl hyu h
  have hy2 : y ^ 2 ≤ 961 := by
    nlinarith [mul_nonneg (show (0:ℤ) ≤ 31 - y by linarith) (show (0:ℤ) ≤ 31 + y by linarith)]
  interval_cases x <;> interval_cases y <;> omega

end Problems.Minif2f.imo_1977_p5
