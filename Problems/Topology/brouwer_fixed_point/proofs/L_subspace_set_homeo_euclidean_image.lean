-- Use the orthonormal-basis-induced linear isometric equivalence
-- `W ≃ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n)` (sub_1, where n = finrank ℝ W) and
-- transport `T` along it. Sub_2 packages the standard preservation facts
-- (image is nonempty/compact/convex with nonempty interior, plus the homeo
-- restriction from e) into one bundle, so the parent is closed by a single
-- ⟨n, e '' T, _⟩ witness. Each sub-goal is strictly simpler: sub_1 is a
-- direct application of Mathlib's `OrthonormalBasis.toLinearIsometryEquiv`
-- (no set-theoretic content), sub_2 is generic in `V` and re-uses
-- continuity/openness/linearity of `e` without touching the existential.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10813

namespace Problems.Topology.brouwer_fixed_point

def subspace_set_homeo_euclidean_image := @Problems.Topology.brouwer_fixed_point.s10813

end Problems.Topology.brouwer_fixed_point
