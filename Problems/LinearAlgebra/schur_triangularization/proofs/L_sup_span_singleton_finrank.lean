import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- sup_span_singleton_finrank: rank of U ⊔ span {v} equals rank U + 1 when v ∉ U,
-- via Submodule.finrank_sup_span_singleton from Mathlib.
theorem sup_span_singleton_finrank :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (U : Submodule K V) (v : V),
      v ∉ U →
      Module.finrank K ((U ⊔ Submodule.span K {v} : Submodule K V))
        = Module.finrank K U + 1 := by
  intro K _ V _ _ _ U v hv
  exact Submodule.finrank_sup_span_singleton hv

end Problems.LinearAlgebra.schur_triangularization

