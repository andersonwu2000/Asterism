import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_rotation_eigenspace_one_finrank_le_one
import Problems.Geometry.banach_tarski.proofs.L_sphere_inter_finrank_le_one_finite

namespace Problems.Geometry.banach_tarski

-- rotation_fixed_set_on_sphere_finite: fixed points of non-trivial det-1 isometry on sphere
-- are finite; cite rotation_eigenspace_one_finrank_le_one (finrank ker(T-id) ≤ 1) and
-- sphere_inter_finrank_le_one_finite (sphere ∩ finrank-≤1 submodule is finite), then subset.
-- entry_kind: Backward
theorem rotation_fixed_set_on_sphere_finite
    (T : E ≃ₗᵢ[ℝ] E)
    (hdet : LinearMap.det (T.toLinearEquiv.toLinearMap) = 1)
    (hT : T ≠ LinearIsometryEquiv.refl ℝ E) :
    {x ∈ Metric.sphere (0 : E) 1 | T x = x}.Finite := by
  set V := LinearMap.ker (T.toLinearEquiv.toLinearMap - LinearMap.id)
  have hV : Module.finrank ℝ V ≤ 1 :=
    rotation_eigenspace_one_finrank_le_one T hdet hT
  apply Set.Finite.subset (sphere_inter_finrank_le_one_finite V hV)
  rintro x ⟨hx_sph, hTx⟩
  refine ⟨hx_sph, ?_⟩
  rw [LinearMap.mem_ker, LinearMap.sub_apply, LinearMap.id_apply, sub_eq_zero]
  exact hTx

end Problems.Geometry.banach_tarski
