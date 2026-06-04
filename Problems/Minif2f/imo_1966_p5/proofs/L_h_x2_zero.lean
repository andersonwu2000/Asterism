-- Direct sorry-free proof of `x 2 = 0` (leaf-bypass — no sub-goals).
-- Strategy: rewrite all abs terms via the ordering a₁>a₂>a₃>a₄, then take two
-- linear combinations of the equations:
--   `h₁₁ - h₁₀` ⇒ (a₂-a₃)·(x₁+x₂-x₃-x₄) = 0 ⇒ x₁+x₂ = x₃+x₄  (divide by a₂-a₃≠0)
--   `h₁₀ - h₉ ` ⇒ (a₁-a₂)·(x₁-x₂-x₃-x₄) = 0 ⇒ x₁ = x₂+x₃+x₄    (divide by a₁-a₂≠0)
-- Substituting the second into the first: 2·x 2 = 0 ⇒ x 2 = 0 (closed by `linarith`).
import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs._strategy_s9642

namespace Problems.Minif2f.imo_1966_p5

def h_x2_zero := @Problems.Minif2f.imo_1966_p5.s9642

end Problems.Minif2f.imo_1966_p5
