-- Direct proof (leaf): tail of a reduced word is reduced.
-- Rewrite `reduce (x :: M)` via `reduce.cons` and case on `reduce M`.
--   • `reduce M = []`  : then `[x] = x :: M`, so `M = []` and `reduce M = M`.
--   • `reduce M = hd :: tl` : `reduce.cons` gives an `if`. The cancelling branch
--     forces `reduce M = hd :: x :: M`, contradicting `(reduce M).length ≤ M.length`
--     (`reduce.red` + `Red.length`); the non-cancelling branch gives `x :: hd :: tl = x :: M`,
--     whence `hd :: tl = M`, i.e. `reduce M = M`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11401

namespace Problems.Geometry.banach_tarski

def reduce_cons_tail_reduced := @Problems.Geometry.banach_tarski.s11401

end Problems.Geometry.banach_tarski
