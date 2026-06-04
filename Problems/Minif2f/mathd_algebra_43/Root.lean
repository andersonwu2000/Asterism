-- Direct linear-algebra closure: f is affine (f x = a*x + b), so f 7 = 4 and f 6 = 3
-- give a 2×2 linear system in (a, b) with unique solution a = 1, b = -3, hence
-- f 3 = 3·1 + (-3) = 0. We substitute h₀ into h₁, h₂, and the goal, then linarith
-- solves the resulting linear system over ℝ. No sub-goals: this is a leaf — a single
-- linarith call discharges 3a+b = 0 from 7a+b = 4 and 6a+b = 3.
import Mathlib
import Problems.Minif2f.mathd_algebra_43.Defs
import Problems.Minif2f.mathd_algebra_43.proofs._strategy_s670

namespace Problems.Minif2f.mathd_algebra_43

def main := @Problems.Minif2f.mathd_algebra_43.s670

end Problems.Minif2f.mathd_algebra_43
