-- Decompose: extract x = 1/5, y = 24, z = 5/24 from the positive AIME system,
-- then substitute into h₄ : z + 1/y = ↑m to reduce to (↑m : ℝ) = 1/4, then
-- cast back to ℚ. Each sub-goal is independent of m, h₄, h₅.
import Mathlib
import Problems.Minif2f.aimeI_2000_p7.Defs
import Problems.Minif2f.aimeI_2000_p7.proofs._strategy_s9395

namespace Problems.Minif2f.aimeI_2000_p7

def m_eq_one_quarter := @Problems.Minif2f.aimeI_2000_p7.s9395

end Problems.Minif2f.aimeI_2000_p7
