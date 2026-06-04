-- Split by variable a/b/c into three independent Pisano-residue lemmas:
-- `t a % 7 = 5`, `t b % 7 = 6`, `t c % 7 = 1`, since the Fibonacci-like
-- sequence `t` has Pisano period 16 mod 7, and 5+6+1 = 12 ≡ 5 (mod 7).
-- Combinator: omega on the three modular residues.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs._strategy_s9309

namespace Problems.Minif2f.mathd_numbertheory_405

def main := @Problems.Minif2f.mathd_numbertheory_405.s9309

end Problems.Minif2f.mathd_numbertheory_405
