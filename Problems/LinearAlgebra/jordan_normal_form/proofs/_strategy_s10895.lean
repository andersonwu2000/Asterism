import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_glue_maxgen_jordan_blocks
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_maxgen_eigenspace_invariant
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_restriction_has_jordan_basis

namespace Problems.LinearAlgebra.jordan_normal_form

-- Assembly (Brick C, step 4): glue per-eigenspace Jordan bases into a global one.
-- `maxgen_eigenspace_invariant` gives T-stability of each generalized eigenspace, so
-- `T.restrict (hinv μ)` is well-typed. `restriction_has_jordan_basis` (consuming hJordNilp
-- via the μ-shift `T - μ•id` nilpotency) yields a Jordan-form basis on each block;
-- `glue_maxgen_jordan_blocks` collects these along `hdec` into a block-diagonal global
-- matrix and reindexes blocks contiguously, which is again Jordan form.
theorem s10895
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hJordNilp : ∀ μ : K,
        ∀ (N : (Module.End.maxGenEigenspace T μ : Submodule K V) →ₗ[K]
                (Module.End.maxGenEigenspace T μ : Submodule K V)),
          IsNilpotent N →
          ∃ b : Module.Basis
                  (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))
                  K (Module.End.maxGenEigenspace T μ : Submodule K V),
            IsJordanForm (LinearMap.toMatrix b b N) ∧
            ∀ i, (LinearMap.toMatrix b b N) i i = 0) :
    ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b b T)  := by
  have hinv := maxgen_eigenspace_invariant T
  have hblock := restriction_has_jordan_basis T hJordNilp hinv
  exact glue_maxgen_jordan_blocks T hdec hinv hblock

end Problems.LinearAlgebra.jordan_normal_form
