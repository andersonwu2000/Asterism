import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs

namespace Problems.LinearAlgebra.rational_canonical_form

-- dfinsupp_basis_diag_component: j-th component of DFinsupp.basis ⟨j,l⟩ equals the j-th basis
-- vector (pb j) l; proved by unfolding Basis.ofRepr repr via symm_trans_apply + mapRange_single
-- + sigmaFinsuppEquivDFinsupp_single + DFinsupp.single_eq_same chain.
-- entry_kind: Builder
theorem dfinsupp_basis_diag_component {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim) :
    (DFinsupp.basis fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j
      = (AdjoinRoot.powerBasis' (hmonic j)).basis l := by
  change ((DFinsupp.basis fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis).repr.symm
      (Finsupp.single ⟨j, l⟩ 1)) j = _
  simp only [DFinsupp.basis, LinearEquiv.symm_trans_apply,
    DFinsupp.mapRange.linearEquiv_symm, LinearEquiv.symm_symm,
    DFinsupp.mapRange.linearEquiv_apply, DFinsupp.mapRange_apply,
    sigmaFinsuppLequivDFinsupp_apply, AddEquiv.toFun_eq_coe,
    sigmaFinsuppAddEquivDFinsupp_apply,
    sigmaFinsuppEquivDFinsupp_single, DFinsupp.single_eq_same]
  exact rfl

end Problems.LinearAlgebra.rational_canonical_form
