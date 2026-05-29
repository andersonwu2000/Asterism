-- Prepend letter `x` to reduced nonempty tail `M`, carrying the head-keyed mod-3 residue
-- invariant from `M` to `x :: M`, via 2 strictly-simpler sub-goals.
--   `cons_head_ne_inv`     — FreeGroup combinatorics: a reduced `x :: M` cannot have `M`
--     start with `x`'s inverse `(x.1, !x.2)` (Red.Step.not cancellation + length).
--   `cons_residue_arith`   — pure ℤ/`Int.ModEq` core: with that head-inequality replacing
--     the FreeGroup reduce equation, `step x (p,q,r)` (= foldr over `x :: M`) satisfies the
--     head-keyed invariant; `hhead` + `hclass` + `¬3∣q` prune the residue state that would
--     make `3 ∣ q'`.
-- Combinator: derive `hhead` from reducedness, then hand the arithmetic the clean hypothesis.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11403

namespace Problems.Geometry.banach_tarski

def cons_residue_step := @Problems.Geometry.banach_tarski.s11403

end Problems.Geometry.banach_tarski
