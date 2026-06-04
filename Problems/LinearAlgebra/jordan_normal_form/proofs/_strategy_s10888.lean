import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_chain_basis_exists
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_chain_basis_matrix_form

namespace Problems.LinearAlgebra.jordan_normal_form

-- Split into (1) existence of a "Jordan-chain" basis structure for the nilpotent N,
-- and (2) a matrix-translation lemma converting that structure to IsJordanForm + diag=0.
-- Sub-goal 1 is the hard linear-algebra existence (kernel-filtration / chain construction)
-- expressed structurally without any matrix vocabulary — strictly simpler than the parent.
-- Sub-goal 2 is a pure matrix-level computation given the structural hypothesis: each
-- column of toMatrix b b N is either zero or a standard basis vector e_{j-1}, which
-- immediately yields the IsJordanForm shape and zero diagonal.
theorem s10888
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      IsJordanForm (LinearMap.toMatrix b b N) ∧
    ∀ i : Fin (Module.finrank K W), (LinearMap.toMatrix b b N) i i = 0  := by
  have h_exists := jordan_chain_basis_exists N hN
  obtain ⟨b, hb⟩ := h_exists
  have h_matrix := jordan_chain_basis_matrix_form N hN b hb
  exact ⟨b, h_matrix.1, h_matrix.2⟩

end Problems.LinearAlgebra.jordan_normal_form
