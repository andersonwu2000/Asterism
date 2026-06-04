-- Direct algebraic identity over ℝ with x ≠ 0; no decomposition needed.
-- `field_simp` uses h₀ to clear all denominators, reducing the goal to a
-- polynomial identity in x which `ring` closes.
-- LHS simplifies to (x/4) * (9 x^4) * (8 x^3) = 72 x^8 / 4 = 18 x^8 = RHS.
import Mathlib
import Problems.Minif2f.mathd_algebra_245.Defs
import Problems.Minif2f.mathd_algebra_245.proofs._strategy_s654

namespace Problems.Minif2f.mathd_algebra_245

def main := @Problems.Minif2f.mathd_algebra_245.s654

end Problems.Minif2f.mathd_algebra_245
