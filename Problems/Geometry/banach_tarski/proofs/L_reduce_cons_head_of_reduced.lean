-- Direct proof via `FreeGroup.reduce.cons`: rewrite `reduce (x :: L)` and use `hL` to
-- collapse `reduce L` to `L`, then case on `L`. The nil case is `simp`; the cons case
-- splits on the cancellation condition. The only content needing `hL` (reducedness) is
-- `h_reduced`: a reduced `hd :: tl` cannot have `tl` start with `hd`'s inverse — proved by
-- exhibiting the `Red.Step.not` cancellation and deriving a length contradiction from
-- `reduce.eq_of_red` + `Red.length`. Builds sorry-free; shipped as a leaf.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11386

namespace Problems.Geometry.banach_tarski

def reduce_cons_head_of_reduced := @Problems.Geometry.banach_tarski.s11386

end Problems.Geometry.banach_tarski
