import Mathlib
import Problems.Minif2f.mathd_numbertheory_543.Defs
import Problems.Minif2f.mathd_numbertheory_543.proofs.L_card_divisors_thirty_pow_four

namespace Problems.Minif2f.mathd_numbertheory_543

-- Reduce ∑_{k ∈ divisors n} 1 to (Nat.divisors n).card, then close 125 - 2 = 123.
-- Single sub-goal: τ(30^4) = 125. Strictly simpler — drops the subtraction and
-- exposes the divisor-count multiplicativity structure (30^4 = 2^4·3^4·5^4, so
-- τ = 5·5·5 = 125) which the Builder closes by prime-power decomposition.
theorem s9381 : (∑ k ∈ Nat.divisors (30 ^ 4), 1) - 2 = 123  := by
  have h_card : (Nat.divisors (30 ^ 4)).card = 125 :=
    card_divisors_thirty_pow_four
  rw [← Finset.card_eq_sum_ones, h_card]

end Problems.Minif2f.mathd_numbertheory_543
