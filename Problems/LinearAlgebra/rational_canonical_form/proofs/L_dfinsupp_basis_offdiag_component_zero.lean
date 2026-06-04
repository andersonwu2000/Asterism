import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs

namespace Problems.LinearAlgebra.rational_canonical_form

-- dfinsupp_basis_offdiag_component_zero: off-diagonal component of a DFinsupp.basis vector
-- is zero; proved via repr injectivity + LinearEquiv.apply_symm_apply + Finsupp.single_eq_of_ne.
-- entry_kind: Builder
theorem dfinsupp_basis_offdiag_component_zero {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (h : i' ≠ j) :
    ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i' = 0 := by
  apply (AdjoinRoot.powerBasis' (hmonic i')).basis.repr.injective
  ext k'
  simp only [map_zero, Finsupp.coe_zero, Pi.zero_apply]
  have repr_formula : (AdjoinRoot.powerBasis' (hmonic i')).basis.repr
      (((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i') k' =
      (DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr
        ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) ⟨i', k'⟩ :=
    rfl
  rw [repr_formula]
  have hrepr_self : (DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr
      ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) =
      Finsupp.single ⟨j, l⟩ 1 := LinearEquiv.apply_symm_apply _ _
  rw [hrepr_self]
  exact Finsupp.single_eq_of_ne (fun heq => h (Sigma.mk.inj heq).1)

end Problems.LinearAlgebra.rational_canonical_form
