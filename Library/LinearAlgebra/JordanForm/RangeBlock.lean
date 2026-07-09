import Library.LinearAlgebra.JordanForm.ChainPartition
import Library.LinearAlgebra.JordanForm.FamilyConstruction
import Mathlib

/-!
# Range block structure for nilpotent operators

This file constructs a strongly-structured block Jordan chain basis for the range of a
nilpotent linear map `N : W →ₗ[K] W`, then lifts it to a full Jordan chain basis of `W`.
The key steps are: (1) reindex a flat consecutive-chain basis of `range N` into proper
chain-blocks via a combinatorial partition, and (2) use rank-nullity to bound
`finrank (range N)`, enabling the inductive assembly in `FamilyConstruction`.
-/

open Library.LinearAlgebra.JordanForm.ChainPartition
open Library.LinearAlgebra.JordanForm.FamilyConstruction

namespace Library.LinearAlgebra.JordanForm.RangeBlock

variable {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
variable (N : W →ₗ[K] W)

/-- Given a flat consecutive-chain basis `bU` of `range N` and a combinatorial block partition
`(p, l, e, o)` of its index type, the reindexed basis `bU.reindex e` satisfies the strong
Jordan chain property: each block element either starts the chain (index `j = 0` and maps to
zero) or maps to its immediate predecessor within the same block. -/
theorem chain_block_assemble
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i)
    (p : ℕ) (l : Fin p → ℕ)
    (e : Fin (Module.finrank K (LinearMap.range N)) ≃ Σ t : Fin p, Fin (l t))
    (o : Fin p → ℕ)
    (hoff : ∀ q : Fin (Module.finrank K (LinearMap.range N)),
        (q : ℕ) = o (e q).1 + ((e q).2 : ℕ))
    (halign : ∀ q : Fin (Module.finrank K (LinearMap.range N)),
        ((N.restrict h_inv) (bU q) = 0 ↔ ((e q).2 : ℕ) = 0)) :
    ∃ (p : ℕ) (l : Fin p → ℕ)
      (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N)),
      ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
      (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩ := by
  refine ⟨p, l, bU.reindex e, ?_⟩
  intro t j
  have heq : e (e.symm ⟨t, j⟩) = ⟨t, j⟩ := e.apply_symm_apply _
  have hreq : (bU.reindex e) ⟨t, j⟩ = bU (e.symm ⟨t, j⟩) := bU.reindex_apply e _
  have hoffj := hoff (e.symm ⟨t, j⟩)
  rw [heq] at hoffj
  dsimp only at hoffj
  rcases hbU (e.symm ⟨t, j⟩) with hzero | ⟨i, hi1, hi2⟩
  · left
    have hj0 := (halign (e.symm ⟨t, j⟩)).mp hzero
    rw [heq] at hj0
    dsimp only at hj0
    exact ⟨hj0, by rw [hreq]; exact hzero⟩
  · right
    have hjpos : (j : ℕ) ≠ 0 := by
      intro h0
      have hz : (N.restrict h_inv) (bU (e.symm ⟨t, j⟩)) = 0 := by
        apply (halign (e.symm ⟨t, j⟩)).mpr
        rw [heq]; dsimp only; exact h0
      rw [hi2] at hz
      exact bU.ne_zero i hz
    have hlt : (j : ℕ) - 1 < l t := by omega
    refine ⟨⟨(j : ℕ) - 1, hlt⟩, ?_, ?_⟩
    · change (j : ℕ) - 1 + 1 = (j : ℕ); omega
    · have hidx : i = e.symm ⟨t, ⟨(j : ℕ) - 1, hlt⟩⟩ := by
        apply Fin.ext
        have hoffi := hoff (e.symm ⟨t, ⟨(j : ℕ) - 1, hlt⟩⟩)
        rw [e.apply_symm_apply] at hoffi
        dsimp only at hoffi
        omega
      rw [hreq, hi2, bU.reindex_apply, hidx]

/-- In any flat consecutive-chain basis `bU` of `range N`, the element at index `0` maps to
zero under `N.restrict h_inv`, since no index `i` can satisfy `i + 1 = 0`. -/
theorem zero_index_maps_to_zero
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∀ q : Fin (Module.finrank K (LinearMap.range N)),
        (q : ℕ) = 0 → (N.restrict h_inv) (bU q) = 0 := by grind

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
/-- Given a flat consecutive-chain basis `bU` of `range N` (where each basis vector either
maps to zero or to its flat predecessor), produces a reindexed block basis `d` satisfying
the strong Jordan chain property: each block starts at index `0` (mapping to zero) and
each interior element maps to the preceding element of the same block. -/
theorem range_block_strong
    (hN : IsNilpotent N)
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

-- range_finrank_le: rank-nullity + nilpotent-surjective collapse forces finrank(range N) ≤ m
-- If N were injective (ker = ⊥), finite-dim gives surjective, so N^k surjective;
-- but N^k = 0 maps everything to 0, forcing W trivial → N = 0, contradicting hN0.
-- Hence ker N ≠ ⊥, so finrank(ker N) ≥ 1, and rank-nullity gives the bound.
/-- A nilpotent non-zero operator on a space of dimension at most `m + 1` has range of
dimension at most `m`; the kernel is non-trivial by injectivity-surjectivity collapse, and
rank-nullity yields the bound. -/
theorem range_finrank_le
    (hN : IsNilpotent N) (hN0 : N ≠ 0) {m : ℕ}
    (hdim : Module.finrank K W ≤ m + 1) :
    Module.finrank K (LinearMap.range N) ≤ m := by
  have hiter_eq_pow : ∀ k : ℕ, (N : W → W) ^[k] = ⇑(N ^ k) := fun k => by
    induction k with
    | zero => ext x; simp
    | succ n ih => ext x; simp [pow_succ, Function.comp, Module.End.mul_apply, ← ih]
  have hker_ne_bot : LinearMap.ker N ≠ ⊥ := by
    intro hbot
    have hinj : Function.Injective N := LinearMap.ker_eq_bot.mp hbot
    have hsurj : Function.Surjective (N : W → W) :=
      LinearMap.injective_iff_surjective.mp hinj
    obtain ⟨k, hk⟩ := hN
    have hpow_surj : Function.Surjective ((N : W → W) ^[k]) := hsurj.iterate k
    rw [hiter_eq_pow, hk] at hpow_surj
    have hsub : ∀ w : W, w = 0 := fun w => by
      obtain ⟨v, hv⟩ := hpow_surj w
      simp [LinearMap.zero_apply] at hv
      exact hv.symm
    exact hN0 (LinearMap.ext (fun x => by simp [hsub x]))
  have hrn : Module.finrank K (LinearMap.range N) + Module.finrank K (LinearMap.ker N) =
      Module.finrank K W := LinearMap.finrank_range_add_finrank_ker N
  have hker_pos : 1 ≤ Module.finrank K (LinearMap.ker N) := by
    rw [Nat.one_le_iff_ne_zero]
    exact fun h => hker_ne_bot (Submodule.finrank_eq_zero.mp h)
  omega

/-- The restriction of a nilpotent endomorphism to its own range is again nilpotent. -/
theorem range_restrict_nilpotent
    (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N) :
    IsNilpotent (N.restrict h_inv) := Module.End.isNilpotent.restrict h_inv hN

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
/-- Given a nilpotent non-zero operator `N` and a flat consecutive-chain basis `bU` of
`range N`, produces a Jordan chain basis of all of `W`: the chains in `range N` are first
reorganised into proper blocks via `range_block_strong`, then lifted to `W` by
`assemble_block_jordan_strong`. -/
theorem block_jordan_basis_exists
    (hN : IsNilpotent N) (hN0 : N ≠ 0)
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

end Library.LinearAlgebra.JordanForm.RangeBlock
