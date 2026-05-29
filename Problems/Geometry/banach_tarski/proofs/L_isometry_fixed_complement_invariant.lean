-- A linear isometry equiv preserving a finite-dim submodule W also preserves Wᗮ.
-- Single sub-goal: T maps W *onto* W (injective + equal finrank ⇒ surjective onto W).
-- Closer: x ∈ Wᗮ, w ∈ W; write w = T y with y ∈ W, then ⟪w, T x⟫ = ⟪T y, T x⟫ =
-- ⟪y, x⟫ = 0 by inner_map_map and x ∈ Wᗮ. The onto-W fact is the only real work.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11421

namespace Problems.Geometry.banach_tarski

def isometry_fixed_complement_invariant := @Problems.Geometry.banach_tarski.s11421

end Problems.Geometry.banach_tarski
