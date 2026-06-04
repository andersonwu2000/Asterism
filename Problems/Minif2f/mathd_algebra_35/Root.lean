-- Direct computation: q 2 = 6/2 = 3 via h₁ (with 2 ≠ 0), then p 3 = 2 - 3^2 = -7 via h₀.
-- Leaf-bypass: pure substitution + arithmetic, no sub-goals — `rw [h₀, h₁ 2 ...]; norm_num` closes it.
import Mathlib
import Problems.Minif2f.mathd_algebra_35.Defs
import Problems.Minif2f.mathd_algebra_35.proofs._strategy_s663

namespace Problems.Minif2f.mathd_algebra_35

def main := @Problems.Minif2f.mathd_algebra_35.s663

end Problems.Minif2f.mathd_algebra_35
