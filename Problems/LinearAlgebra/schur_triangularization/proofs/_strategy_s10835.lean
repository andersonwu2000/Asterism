import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_adapted_basis_of_flag
import Problems.LinearAlgebra.schur_triangularization.proofs.L_invariant_flag_exists

namespace Problems.LinearAlgebra.schur_triangularization

-- Decompose into (1) existence of a T-invariant complete flag — a chain of
-- T-invariant subspaces W_i ≤ V with W_0 = ⊥, monotone, dim W_i = min i n —
-- and (2) extracting an adapted basis from such a flag by picking one
-- representative at each step. Sub-goal (1) carries the alg-closed + induction
-- (eigenvalue extraction, quotient endomorphism). Sub-goal (2) is pure linear
-- algebra (no alg-closed needed): pick a vector in W (i+1) \ W i at each step.
theorem s10835 : ∀ {K : Type*} [Field K] [IsAlgClosed K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
    ∀ j : Fin (Module.finrank K V),
      T (b j) ∈ Submodule.span K (b '' Set.Iic j)  := by
  intro K _ _ V _ _ _ T
  obtain ⟨W, hW0, hWmono, hWdim, hWinv⟩ := invariant_flag_exists T
  exact adapted_basis_of_flag T W hW0 hWmono hWdim hWinv

end Problems.LinearAlgebra.schur_triangularization
