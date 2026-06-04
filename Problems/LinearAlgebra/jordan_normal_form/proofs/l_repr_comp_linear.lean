import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- repr_comp_linear: lifts basis-vector identity (d.repr ∘ M ∘ d)_a = (d.repr ∘ d)_b to all w
-- Both coord functionals are K-linear; Basis.ext equates them from the basis-vector hypothesis.
-- entry_kind: Builder
theorem repr_comp_linear
    {K R ι : Type*} [Field K] [AddCommGroup R] [Module K R]
    (M : R →ₗ[K] R) (d : Module.Basis ι K R) (a b : ι)
    (h : ∀ idx : ι, d.repr (M (d idx)) a = d.repr (d idx) b) :
    ∀ w : R, d.repr (M w) a = d.repr w b := by
  intro w
  suffices h' : ((Finsupp.lapply a).comp (d.repr.toLinearMap.comp M) : R →ₗ[K] K) =
               (Finsupp.lapply b).comp d.repr.toLinearMap from
    congr_fun (congr_arg DFunLike.coe h') w
  apply d.ext
  intro idx
  simp [h idx]

end Problems.LinearAlgebra.jordan_normal_form
