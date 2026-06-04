import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- inf_ker_restrict_bridge: p ⊓ ker f and ker (f.restrict hf) have the same finrank
-- via map_comap_subtype (the map of the comap under p.subtype equals p ⊓ ker f)
-- and finrank_map_subtype_eq (injective subtype preserves finrank).
theorem inf_ker_restrict_bridge
    {K M : Type*} [Field K] [AddCommGroup M] [Module K M] [FiniteDimensional K M]
    (f : M →ₗ[K] M) (p : Submodule K M) (hf : ∀ x ∈ p, f x ∈ p) :
    Module.finrank K (p ⊓ LinearMap.ker f : Submodule K M)
      = Module.finrank K ↥(LinearMap.ker (f.restrict hf)) := by
  rw [LinearMap.ker_restrict hf]
  rw [← Submodule.map_comap_subtype p (LinearMap.ker f)]
  rw [Submodule.finrank_map_subtype_eq]

end Problems.LinearAlgebra.jordan_normal_form
