-- Conjugate the linear isometry `R` by the translation `x ↦ x - c`.
-- Build the `IsometryEquiv` explicitly: `toFun x = R (x - c) + c`, inverse
-- `y ↦ R.symm (y - c) + c`; the two `left/right_inv` close by `simp`, and the
-- isometry law reduces to `R`'s isometry plus translation-invariance of `edist`
-- (`edist_add_right`/`edist_sub_right`). The pointwise formula then holds by `rfl`.
-- Direct leaf — no sub-goals.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11518

namespace Problems.Geometry.banach_tarski

def exists_conjugated_isometry := @Problems.Geometry.banach_tarski.s11518

end Problems.Geometry.banach_tarski
