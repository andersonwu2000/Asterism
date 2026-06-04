-- Direct proof: three independent inequalities from `0 < x, y, z` and pairwise-distinct.
-- (1) `0 < a` from positivity of `x + y + z = a` via `linarith`.
-- (2) `b^2 < a^2` since `a^2 - b^2 = 2(xy + yz + zx) > 0` (each cross term positive).
-- (3) `a^2 < 3 b^2` since `3 b^2 - a^2 = (x-y)^2 + (y-z)^2 + (z-x)^2 > 0`
--     (each square strictly positive from `x ≠ y, y ≠ z, z ≠ x`).
-- Hypothesis `h₆ : x * y = z^2` is unused. Ships as a sorry-free direct proof
-- (leaf-bypass), so no sub-goal files are emitted.
import Mathlib
import Problems.Minif2f.imo_1961_p1.Defs
import Problems.Minif2f.imo_1961_p1.proofs._strategy_s9252

namespace Problems.Minif2f.imo_1961_p1

def main := @Problems.Minif2f.imo_1961_p1.s9252

end Problems.Minif2f.imo_1961_p1
