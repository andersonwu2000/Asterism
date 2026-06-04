import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_assemble_block_jordan_strong
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_range_block_strong

namespace Problems.LinearAlgebra.jordan_normal_form

-- Glue `bU` (consecutive Jordan basis of `range N`) up to a block Jordan basis of `W`.
-- Fix over dead s10925: its block reindex exposed only the WEAK chain interface (the `= 0`
-- branch unconstrained in `j`), which admits degenerate non-chains (interior vectors mapping
-- to `0`) and so makes the downstream `card index = finrank W` count FALSE. Here the reindex
-- is strengthened: the `= 0` branch is forced to `j = 0` (proper kernel-filtration chains).
--   * `range_block_strong`: pure index reindex of `bU` into proper chain-blocks `d` (STRONG
--     `hd`). Simpler: no W-level LA, just Fin/ℕ block bookkeeping over an existing basis.
--   * `assemble_block_jordan_strong`: the LA chain-glue — lift chain tops through `N`, extend
--     `ker N`, assemble. Simpler: the chains arrive explicit and STRONG, so the count closes.
-- Combine: obtain the strong block basis of `range N`, feed it to the strong glue.
theorem s10970
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (hN0 : N ≠ 0)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∃ (r : ℕ) (k : Fin r → ℕ)
      (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W),
      ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩  := by
  obtain ⟨p, l, d, hd⟩ := range_block_strong N hN h_inv bU hbU
  exact assemble_block_jordan_strong N hN h_inv p l d hd

end Problems.LinearAlgebra.jordan_normal_form
