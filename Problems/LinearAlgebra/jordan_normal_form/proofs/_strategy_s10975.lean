import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_block_assemble
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_block_partition
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_zero_index_maps_to_zero

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reindex the flat consecutive-chain basis `bU` of `range N` into proper chain-blocks.
-- The flat hypothesis `hbU` (each `bU j` maps to `0` or to its predecessor `bU (j-1)`)
-- already lays the chains end-to-end on `Fin n`; we only need to cut `Fin n` at the
-- "start" indices (`N.restrict (bU q) = 0`) into contiguous blocks.
--   * `zero_index_maps_to_zero`: index 0 is a start (the `∃ i, i+1 = 0` branch is empty),
--     supplying the `h0` the combinatorial partition needs. Simpler: one `hbU` case split.
--   * `chain_block_partition`: pure ℕ/Fin/Equiv combinatorics — cut `Fin n` at the start
--     set into blocks `(p, l)` with reindex `e`, offsets `o`, and the alignment
--     `S q ↔ (e q).2 = 0`. Simpler: no module/linear-map content at all.
--   * `chain_block_assemble`: with the partition handed over, set `d := bU.reindex e` and
--     read off the STRONG chain property index-by-index (alignment gives the `j=0` start
--     and rules out interior starts; `hbU` + the offset formula match interiors to
--     predecessors). Simpler: the combinatorial construction is already done.
theorem s10975
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∃ (p : ℕ) (l : Fin p → ℕ)
      (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N)),
      ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩ := by
  obtain ⟨p, l, e, o, hoff, halign⟩ :=
    chain_block_partition (fun q => (N.restrict h_inv) (bU q) = 0)
      (zero_index_maps_to_zero N h_inv bU hbU)
  exact chain_block_assemble N h_inv bU hbU p l e o hoff halign

end Problems.LinearAlgebra.jordan_normal_form
