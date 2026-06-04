import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_basis_to_consecutive
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_jordan_basis_exists

namespace Problems.LinearAlgebra.jordan_normal_form

-- Glue `bU` (Jordan basis of `range N`) up to a Jordan basis of `W` in two stages,
-- separating the linear-algebra content from the index layout that sank prior attempts.
--   * `block_jordan_basis_exists` (LA chain-glue): lift chain tops through `N`, extend
--     `ker N`, assemble a Jordan basis of `W` indexed by genuine `Σ s : Fin r, Fin (k s)`
--     blocks — each `Fin (k s)` is a chain and `N` strictly decrements the within-block
--     index. Simpler than the parent: it carries no `Fin (finrank W)`-consecutiveness
--     constraint, so the painful index layout is out of the way. The block form makes
--     π-cycles and `some`-collisions (which made the predecessor form of dead `s10921`
--     insufficient) impossible by construction.
--   * `block_basis_to_consecutive` (index layout): reindex any block-form Jordan basis to
--     the `Fin (finrank W)` consecutive form, reusing the proved `block_enum_consecutive`
--     brick. Simpler than the parent: pure index bookkeeping over a basis already given.
-- Combine: `obtain` the block basis, then `exact` the reindexed consecutive basis.
theorem s10924
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (hN0 : N ≠ 0)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  obtain ⟨r, k, c, hc⟩ := block_jordan_basis_exists N hN hN0 h_inv bU hbU
  exact block_basis_to_consecutive N r k c hc

end Problems.LinearAlgebra.jordan_normal_form
