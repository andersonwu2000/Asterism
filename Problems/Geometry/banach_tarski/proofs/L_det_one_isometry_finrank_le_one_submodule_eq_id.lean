-- Thin bridge over the proved scalar law `endo_finrank_le_one_eq_det_smul`:
-- restrict `T` to the ≤1-dim invariant `W`, so `T.restrict hinv : ↥W →ₗ ↥W`
-- acts as `(det) • ·`; `hdet` collapses the scalar to `1`, giving `T x = x` on `W`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11427

namespace Problems.Geometry.banach_tarski

def det_one_isometry_finrank_le_one_submodule_eq_id := @Problems.Geometry.banach_tarski.s11427

end Problems.Geometry.banach_tarski
