-- Direct proof (leaf): tail of a reduced word is reduced.
-- Rewrite `reduce (x :: M)` via `reduce.cons` and case on `reduce M`; the cancelling
-- branch contradicts `(reduce M).length ≤ M.length`, the other gives `reduce M = M`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11404

namespace Problems.Geometry.banach_tarski

def tail_of_reduced_is_reduced := @Problems.Geometry.banach_tarski.s11404

end Problems.Geometry.banach_tarski
