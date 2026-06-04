import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_dfinsupp_basis_diag_component

namespace Problems.LinearAlgebra.rational_canonical_form

-- Diagonal component of the `X`-action: peel the `lsmul`/`restrictScalars`/`DirectSum.smul`
-- wrappers (`restrictScalars_apply`, `lsmul_apply`, `DirectSum.smul_apply` pinned to the
-- `Submodule.span` fiber family), reducing the goal to `X • eⱼₗ-component = root fⱼ * basis l`.
-- The `X`-smul (on `K[X] ⧸ Submodule.span {fⱼ}`) is defeq to `root fⱼ * ·` (the `AdjoinRoot`
-- multiplication), so `change` rephrases the LHS as `root fⱼ * component` and `congrArg`
-- transports the single remaining fact:
--   `dfinsupp_basis_diag_component` — the `j`-th component of `DFinsupp.basis pb ⟨j,l⟩` is
--   `pb j l`. That sub-goal is a pure `DFinsupp.basis` evaluation (no `X`-action, no quotient
--   seam) — strictly simpler than the parent. The `X•·`/`root*·` instance bridge stays inline
--   here (it is unstatable as a standalone single-variable lemma).
theorem s11598 {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim) :
    ((LinearMap.lsmul (Polynomial K)
        (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
        Polynomial.X).restrictScalars K)
      ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) j
      = AdjoinRoot.root (f j) * (AdjoinRoot.powerBasis' (hmonic j)).basis l  := by
  rw [LinearMap.restrictScalars_apply, LinearMap.lsmul_apply]
  rw [DirectSum.smul_apply (M := fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})
      Polynomial.X _ j]
  have hcomp : (DFinsupp.basis fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j
      = (AdjoinRoot.powerBasis' (hmonic j)).basis l :=
    dfinsupp_basis_diag_component f hmonic j l
  change AdjoinRoot.root (f j) *
      ((DFinsupp.basis fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j)
      = AdjoinRoot.root (f j) * (AdjoinRoot.powerBasis' (hmonic j)).basis l
  exact congrArg (fun w => AdjoinRoot.root (f j) * w) hcomp

end Problems.LinearAlgebra.rational_canonical_form
