import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs

namespace Problems.LinearAlgebra.rational_canonical_form

-- entry_kind: Builder
theorem dfinsupp_basis_repr_component {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (g : DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
    (i' : Fin r) (k' : Fin (AdjoinRoot.powerBasis' (hmonic i')).dim) :
    (DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr g ⟨i', k'⟩
      = (AdjoinRoot.powerBasis' (hmonic i')).basis.repr (g i') k' := by noncomm_ring

end Problems.LinearAlgebra.rational_canonical_form
