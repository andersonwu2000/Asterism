import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_dfinsupp_basis_offdiag_component_zero

namespace Problems.LinearAlgebra.rational_canonical_form

-- Off-diagonal component vanishes: the X-action on the direct sum is component-wise,
-- so the i'-th component of `X • eⱼₗ` is `X • (eⱼₗ i')`. The basis vector `eⱼₗ` is
-- supported only on summand `j`, hence its i'-th component (i' ≠ j) is `0`
-- (sub-goal `dfinsupp_basis_offdiag_component_zero`, a pure basis-support fact stripped
-- of the lsmul/restrictScalars layers); `convert smul_zero` then collapses `X • 0`.
theorem s11600 {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (h : i' ≠ j) :
    (((LinearMap.lsmul (Polynomial K)
        (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
        Polynomial.X).restrictScalars K)
      ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩)) i' = 0  := by
  rw [LinearMap.restrictScalars_apply, LinearMap.lsmul_apply,
    DirectSum.smul_apply (M := fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})]
  have hcomp := dfinsupp_basis_offdiag_component_zero f hmonic j l i' h
  convert smul_zero Polynomial.X using 2

end Problems.LinearAlgebra.rational_canonical_form
