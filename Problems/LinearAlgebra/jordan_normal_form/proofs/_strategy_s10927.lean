import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_assemble_block_jordan
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_top_preimages
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_ker_range_complement

namespace Problems.LinearAlgebra.jordan_normal_form

-- Glue a block Jordan basis of `range N` up to a block Jordan basis of all of `W`.
-- Three pieces: (1) `block_top_preimages` — every basis vector of `range N` has an
-- N-preimage (lift chain tops one level higher); (2) `ker_range_complement` — a
-- complement `C` of `range N ⊓ ker N` inside `ker N` (the "new" length-1 chains);
-- (3) `assemble_block_jordan` — with lifts + complement supplied as data, build the
-- block basis of `W` and verify the chain property. Each (1),(2) discharge an
-- existence obligation the parent would otherwise carry, leaving (3) the pure assembly.
theorem s10927
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∃ (r : ℕ) (k : Fin r → ℕ)
      (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W),
      ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩  := by
  obtain ⟨x, hx⟩ := block_top_preimages N hN h_inv p l d hd
  obtain ⟨C, hC1, hC2, hC3⟩ := ker_range_complement N hN h_inv p l d hd
  exact assemble_block_jordan N hN h_inv p l d hd x hx C hC1 hC2 hC3

end Problems.LinearAlgebra.jordan_normal_form
