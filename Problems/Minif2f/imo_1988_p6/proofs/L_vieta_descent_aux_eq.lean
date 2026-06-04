import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs

namespace Problems.Minif2f.imo_1988_p6

-- vieta_descent_aux_eq: lift to ℤ via zify then close by linarith using sq_nonneg hints
-- The identity b²+(kb-a)² = (b(kb-a)+1)k follows from a²+b²=(ab+1)k by ring over ℤ;
-- zify rewrites the ℕ subtraction (using hle : a ≤ k*b) and linarith closes it.
theorem vieta_descent_aux_eq : ∀ (a b k : ℕ), 0 < a → 0 < b → b < a →
    a^2 + b^2 = (a*b + 1) * k → a ≤ k * b →
    b^2 + (k*b - a)^2 = (b * (k*b - a) + 1) * k := by
  intro a b k ha hb hba heq hle
  zify [hle] at *
  linarith [sq_nonneg (a : ℤ), sq_nonneg (b : ℤ), sq_nonneg ((k : ℤ) * b - a)]

end Problems.Minif2f.imo_1988_p6
