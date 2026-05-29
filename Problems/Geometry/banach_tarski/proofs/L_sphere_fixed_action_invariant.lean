-- φ w preserves sphere\D: on-sphere via the isometry φ w fixing 0; off-D via conjugation.
-- If φ v fixed φ w • x for some v ≠ 1, then w⁻¹vw (≠ 1) fixes x, so x ∈ D — contradiction.
-- Direct sorry-free proof (no sub-goals): `map_mul`/`map_inv`/`symm_apply_apply` + `group`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11477

namespace Problems.Geometry.banach_tarski

def sphere_fixed_action_invariant := @Problems.Geometry.banach_tarski.s11477

end Problems.Geometry.banach_tarski
