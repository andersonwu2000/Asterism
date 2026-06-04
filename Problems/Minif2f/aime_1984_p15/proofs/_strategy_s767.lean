import Mathlib
import Problems.Minif2f.aime_1984_p15.Defs

namespace Problems.Minif2f.aime_1984_p15

-- Direct closure via `linear_combination` with Lagrange-interpolation coefficients.
-- Setting s ∈ {4,16,36,64} in
--   (s-1)(s-9)(s-25)(s-49) = (s-4)(s-16)(s-36)(s-64)
--     + α(s-16)(s-36)(s-64) + β(s-4)(s-36)(s-64)
--     + γ(s-4)(s-16)(s-64) + δ(s-4)(s-16)(s-36)
-- yields α = 315/512, β = 693/256, γ = 3861/512, δ = 6435/256
-- whose sum equals 36 — exactly the conclusion. No sub-goals required.
theorem s767 : ∀ (x y z w : ℝ) (h₀ : x ^ 2 / (2 ^ 2 - 1) + y ^ 2 / (2 ^ 2 - 3 ^ 2) + z ^ 2 / (2 ^ 2 - 5 ^ 2) + w ^ 2 / (2 ^ 2 - 7 ^ 2) = 1) (h₁ : x ^ 2 / (4 ^ 2 - 1) + y ^ 2 / (4 ^ 2 - 3 ^ 2) + z ^ 2 / (4 ^ 2 - 5 ^ 2) + w ^ 2 / (4 ^ 2 - 7 ^ 2) = 1) (h₂ : x ^ 2 / (6 ^ 2 - 1) + y ^ 2 / (6 ^ 2 - 3 ^ 2) + z ^ 2 / (6 ^ 2 - 5 ^ 2) + w ^ 2 / (6 ^ 2 - 7 ^ 2) = 1) (h₃ : x ^ 2 / (8 ^ 2 - 1) + y ^ 2 / (8 ^ 2 - 3 ^ 2) + z ^ 2 / (8 ^ 2 - 5 ^ 2) + w ^ 2 / (8 ^ 2 - 7 ^ 2) = 1), x ^ 2 + y ^ 2 + z ^ 2 + w ^ 2 = 36  := by
  intro x y z w h₀ h₁ h₂ h₃
  linear_combination (315/512)*h₀ + (693/256)*h₁ + (3861/512)*h₂ + (6435/256)*h₃

end Problems.Minif2f.aime_1984_p15
