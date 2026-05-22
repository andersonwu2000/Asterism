import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- quotient_nontrivial_of_finrank_lt: finrank gap implies nontrivial quotient via
-- Submodule.finrank_quotient_add_finrank + Module.nontrivial_of_finrank_pos
-- entry_kind: Builder
theorem quotient_nontrivial_of_finrank_lt :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (U : Submodule K V),
      Module.finrank K U < Module.finrank K V → Nontrivial (V ⧸ U) := by
  intro K _ V _ _ _ U hlt
  have hU_ne_top : U ≠ ⊤ := by
    intro h
    have : Module.finrank K U = Module.finrank K V := by
      conv_lhs => rw [h]
      exact finrank_top K V
    omega
  have hpos : 0 < Module.finrank K (V ⧸ U) := by
    have := Submodule.finrank_quotient_add_finrank U
    omega
  exact Module.nontrivial_of_finrank_pos hpos

end Problems.LinearAlgebra.schur_triangularization
