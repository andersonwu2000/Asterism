-- Strip the group layer, then reduce to a pure `reduce`-of-cons head fact.
-- `hmul` rewrites `(of i)⁻¹ * w` to `mk ((i,false) :: toWord w)` (via `inv_mk`/`mul_mk`)
-- so its `toWord` is `reduce ((i,false) :: toWord w)` — the group algebra is discharged inline.
-- The remaining content is the single sub-goal `reduce_cons_head_of_reduced`: for an already
-- reduced list `L`, prepending a letter `x` keeps `x` as head iff `L` does not start with `x`'s
-- inverse `(x.1, !x.2)`. Instantiated at `x = (i,false)`, `L = toWord w` (reduced by
-- `reduce_toWord`), `(x.1, !x.2) = (i, true)`, closing the parent.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11385

namespace Problems.Geometry.banach_tarski

def head_inv_mul_iff := @Problems.Geometry.banach_tarski.s11385

end Problems.Geometry.banach_tarski
