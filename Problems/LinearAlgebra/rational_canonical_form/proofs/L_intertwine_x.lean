import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs

namespace Problems.LinearAlgebra.rational_canonical_form

-- entry_kind: Builder
-- intertwine_x: AEval'.of T composed with e.restrictScalars K intertwines T with X-multiplication
-- Uses AEval'.X_smul_of (X • of T v = of T (T v)) then e.map_smul to pull X out via K[X]-linearity.
theorem intertwine_x {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) {r : ℕ} (f : Fin r → Polynomial K)
    (e : Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :
    ∀ v : V, ((Module.AEval'.of T).trans (e.restrictScalars K)) (T v)
      = ((LinearMap.lsmul (Polynomial K)
            (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
            Polynomial.X).restrictScalars K)
          (((Module.AEval'.of T).trans (e.restrictScalars K)) v) := by
  intro v
  simp only [LinearEquiv.trans_apply, LinearMap.lsmul_apply,
             LinearMap.restrictScalars_apply]
  rw [← Module.AEval'.X_smul_of]
  exact e.map_smul Polynomial.X _
end Problems.LinearAlgebra.rational_canonical_form
