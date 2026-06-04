-- Strip the divisibility wrapper: extract k from `(a*b+1) ∣ a²+b²`, then defer to
-- the abstracted ℕ-level Vieta-jumping claim `quotient_perfect_square` which states
-- that any k satisfying a²+b² = (ab+1)·k with a,b > 0 must itself be a perfect square.
-- Combinator: trivial — `mul_comm` + use the extracted equation.
import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs._strategy_s9328

namespace Problems.Minif2f.imo_1988_p6

def vieta_jumping_nat := @Problems.Minif2f.imo_1988_p6.s9328

end Problems.Minif2f.imo_1988_p6
