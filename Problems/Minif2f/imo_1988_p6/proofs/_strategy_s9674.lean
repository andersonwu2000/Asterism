import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs.L_vieta_descent_witness

namespace Problems.Minif2f.imo_1988_p6

-- Vieta jump: construct the conjugate root a' (= k·b - a in ℤ) as a ℕ with the
-- descent inequality a' ≤ b and the matching identity b² + a'² = (b·a' + 1)·k.
-- Combinator splits on a' = 0 (forcing k = b², perfect-square branch witnessed by b)
-- vs 0 < a' (descent witnessed by (c, d) = (b, a'); c < a follows from b < a).
theorem s9674 : ∀ (a b k : ℕ), 0 < a → 0 < b → b < a →
    a^2 + b^2 = (a*b + 1) * k →
    (∃ x : ℕ, x^2 = k) ∨
    (∃ c d : ℕ, 0 < c ∧ 0 < d ∧ d ≤ c ∧ c < a ∧
      c^2 + d^2 = (c*d + 1) * k)  := by
  intro a b k ha hb hba heq
  obtain ⟨a', hab_le, heq'⟩ := vieta_descent_witness a b k ha hb hba heq
  rcases Nat.eq_zero_or_pos a' with ha0 | ha_pos
  · left
    refine ⟨b, ?_⟩
    subst ha0
    simpa using heq'
  · right
    exact ⟨b, a', hb, ha_pos, hab_le, hba, heq'⟩

end Problems.Minif2f.imo_1988_p6
