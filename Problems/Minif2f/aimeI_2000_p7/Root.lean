-- Decompose: single sub-goal `m_eq_one_quarter` derives `m = 1/4`
-- from the AIME system; the parent then reduces to the concrete
-- numeric identity `↑(1/4).den + (1/4).num = 5` (= 4 + 1), closed by
-- `native_decide` (only style-linter warning; not an error).
import Mathlib
import Problems.Minif2f.aimeI_2000_p7.Defs
import Problems.Minif2f.aimeI_2000_p7.proofs._strategy_s768

namespace Problems.Minif2f.aimeI_2000_p7

def main := @Problems.Minif2f.aimeI_2000_p7.s768

end Problems.Minif2f.aimeI_2000_p7
