import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_diagonal_reindex_jordan
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_collected_matrix_blockdiagonal

namespace Problems.LinearAlgebra.jordan_normal_form

-- Glue the per-eigenspace Jordan bases into a global Jordan-form basis (Brick C step 4).
-- `collected_matrix_blockdiagonal`: over the collected basis of the internal direct sum
--   `hdec`, the matrix of `T` is block-diagonal with diagonal blocks the per-eigenspace
--   restriction matrices `toMatrix (bμ μ) (bμ μ) (T.restrict (hinv μ))`.
-- `block_diagonal_reindex_jordan`: any basis whose matrix is block-diagonal with each diagonal
--   block already in Jordan form reindexes (blocks laid out contiguously) to a
--   `Fin (finrank V)` basis in global Jordan form.
-- Each sub-goal drops a layer: the first is direct-sum / restriction bookkeeping, the second
-- is pure matrix combinatorics (no eigenspaces, no invariance).
theorem s10897
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (hblock : ∀ μ : K, ∃ b : Module.Basis
          (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) K
          (Module.End.maxGenEigenspace T μ : Submodule K V),
        IsJordanForm (LinearMap.toMatrix b b (T.restrict (hinv μ)))) :
    ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b b T)  := by
  choose bμ hbμ using hblock
  haveI : Fintype ((μ : K) ×
      Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) :=
    FiniteDimensional.fintypeBasisIndex (hdec.collectedBasis bμ)
  have hb := collected_matrix_blockdiagonal T hdec hinv bμ
  exact block_diagonal_reindex_jordan T (hdec.collectedBasis bμ)
    (fun μ => LinearMap.toMatrix (bμ μ) (bμ μ) (T.restrict (hinv μ))) hb hbμ



end Problems.LinearAlgebra.jordan_normal_form
