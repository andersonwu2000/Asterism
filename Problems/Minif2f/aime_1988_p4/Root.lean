-- Sandwich 19 < (n:ℝ) between two real-valued bounds on Σ|aₖ|, then cast.
-- (a) sum_abs_lt_card: Σ|aₖ| < (n:ℝ), since each |aₖ| < 1 and h₁ rules out n=0.
-- (b) nineteen_le_sum_abs: 19 ≤ Σ|aₖ|, since h₁ gives Σ|aₖ| = 19 + |Σaₖ| ≥ 19.
-- Chain: lt_of_le_of_lt → (19:ℝ) < (n:ℝ) → 19 < n in ℕ → omega closes 20 ≤ n.
import Mathlib
import Problems.Minif2f.aime_1988_p4.Defs
import Problems.Minif2f.aime_1988_p4.proofs._strategy_s785

namespace Problems.Minif2f.aime_1988_p4

def main := @Problems.Minif2f.aime_1988_p4.s785

end Problems.Minif2f.aime_1988_p4
