import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs

namespace Problems.Minif2f.imo_1988_p6

-- vieta_descent_aux_le: bound k*b - a ≤ b by reducing to k*b ≤ a+b via nlinarith
-- Reduces to showing b³ ≤ a(b²+1)+b, which follows since a ≥ b+1.
theorem vieta_descent_aux_le : ∀ (a b k : ℕ), 0 < a → 0 < b → b < a →
    a^2 + b^2 = (a*b + 1) * k → a ≤ k * b → k * b - a ≤ b := by
  intro a b k ha hb hba heq hle
  suffices h : k * b ≤ a + b by omega
  nlinarith [sq_nonneg a, sq_nonneg b, sq_nonneg (a - b), Nat.mul_comm a b]

end Problems.Minif2f.imo_1988_p6
