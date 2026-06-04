import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs.L_quotient_perfect_square

namespace Problems.Minif2f.imo_1988_p6

-- Strip the divisibility wrapper: extract k from `(a*b+1) ∣ a²+b²`, then defer to
-- the abstracted ℕ-level Vieta-jumping claim `quotient_perfect_square` which states
-- that any k satisfying a²+b² = (ab+1)·k with a,b > 0 must itself be a perfect square.
-- Combinator: trivial — `mul_comm` + use the extracted equation.
theorem s9328 : ∀ (a b : ℕ) (_h₀ : 0 < a ∧ 0 < b) (_h₁ : a * b + 1 ∣ a ^ 2 + b ^ 2),
    ∃ x : ℕ, x ^ 2 * (a * b + 1) = a ^ 2 + b ^ 2  := by
  intro a b h₀ h₁
  obtain ⟨k, hk⟩ := h₁
  obtain ⟨x, hx⟩ := quotient_perfect_square a b k h₀.1 h₀.2 hk
  refine ⟨x, ?_⟩
  rw [hx, mul_comm]
  exact hk.symm

end Problems.Minif2f.imo_1988_p6
