import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_basis_from_flag_spans
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_vector_seq_exists

namespace Problems.LinearAlgebra.schur_triangularization

-- Decompose into (1) constructing a function v : Fin n → V whose initial spans match the
-- flag, and (2) packaging such a v as a Module.Basis carrying the same property.
-- (1) carries the inductive / dimension-step content (pick v_j ∈ W(j+1) extending v_{<j});
-- (2) is a basis-vs-function bookkeeping bridge: range v spans W n = ⊤ + |Fin n| = finrank,
-- so v is a basis.
theorem s10838 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
        ∀ j : Fin (Module.finrank K V),
          Submodule.span K (b '' Set.Iic j) = W (j.val + 1)  := by
  intro K _ V _ _ _ W hW0 hWmono hWdim
  have h_flag_vector_seq_exists := flag_vector_seq_exists W hW0 hWmono hWdim
  have h_basis_from_flag_spans := basis_from_flag_spans W hW0 hWmono hWdim
  obtain ⟨v, hv⟩ := h_flag_vector_seq_exists
  exact h_basis_from_flag_spans v hv

end Problems.LinearAlgebra.schur_triangularization
