import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- proj_sq_descent: algebraic inequality; from 0 ≤ p*q and p²≤q² conclude (p-q)²≤q²
-- Equivalent to 2pq ≥ p², closed by nlinarith with squared-term hints.
theorem proj_sq_descent : ∀ p q : ℝ, 0 ≤ p * q → p^2 ≤ q^2 → (p - q)^2 ≤ q^2 := by
  intro p q hpq hpq2
  nlinarith [sq_nonneg (p - q), sq_nonneg (p + q), sq_nonneg p, sq_nonneg q, hpq, hpq2]

end Problems.sylvester_gallai
