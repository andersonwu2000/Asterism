import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_lsmul_x_offdiag_component_zero

namespace Problems.LinearAlgebra.rational_canonical_form

-- Off-diagonal repr-zero: reduce to the single component fact that the `i'`-th
-- summand of `X • eⱼₗ` vanishes (`lsmul_x_offdiag_component_zero`), since `i' ≠ j`
-- and the X-action is component-wise; the parent's `repr ... k'` layer then collapses
-- via `map_zero`. The sub-goal drops the outer `repr`/`k'` coordinate — strictly simpler.
theorem s11599 {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (k' : Fin (AdjoinRoot.powerBasis' (hmonic i')).dim) (h : i' ≠ j) :
    (AdjoinRoot.powerBasis' (hmonic i')).basis.repr
      (((LinearMap.lsmul (Polynomial K)
          (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
          Polynomial.X).restrictScalars K)
        ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i') k' = 0  := by
  -- The X-action on `⨁ᵢ K[X]/(fᵢ)` is component-wise and each summand is invariant,
  -- so the `i'`-th component of `X • eⱼₗ` (with `i' ≠ j`) is the zero element of the
  -- `i'`-th fiber; the `repr` of `0` at any coordinate is `0`.
  have hcomp :
      (((LinearMap.lsmul (Polynomial K)
          (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
          Polynomial.X).restrictScalars K)
        ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩)) i' = 0 :=
    lsmul_x_offdiag_component_zero f hmonic j l i' h
  rw [hcomp]
  exact congrFun (congrArg _ (map_zero _)) k'

end Problems.LinearAlgebra.rational_canonical_form
