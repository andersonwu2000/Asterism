import Library.LinearAlgebra.JordanForm.BlockEnum
import Library.LinearAlgebra.JordanForm.Defs
import Mathlib

open Library.LinearAlgebra.JordanForm.BlockEnum
open Library.LinearAlgebra.JordanForm.Defs

namespace Library.LinearAlgebra.JordanForm.BlockDiagonal

-- Entrywise (μ,μ)-diagonal block of the collected-basis matrix.
-- Unfold both `toMatrix` entries; the basis vector `collectedBasis ⟨μ,j⟩` is `↑(bμ μ j)`
-- and `T ↑(bμ μ j) = ↑((T.restrict).._)` by `restrict_apply`; the coordinate of a single-
-- summand element under the collected basis equals its `bμ μ`-coordinate (bridge `hbridge`).
theorem diag_block
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (bμ : ∀ μ : K, Module.Basis
        (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) K
        (Module.End.maxGenEigenspace T μ : Submodule K V))
    [Fintype ((μ : K) × Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))]
    (μ : K)
    (i j : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) :
    LinearMap.toMatrix (hdec.collectedBasis bμ) (hdec.collectedBasis bμ) T ⟨μ, i⟩ ⟨μ, j⟩
      = LinearMap.toMatrix (bμ μ) (bμ μ) (T.restrict (hinv μ)) i j  := by
  have hbridge : ∀ (w : (Module.End.maxGenEigenspace T μ : Submodule K V))
      (k : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))),
      (hdec.collectedBasis bμ).repr (w : V) ⟨μ, k⟩ = (bμ μ).repr w k := by
    intro w k
    let L1 : (Module.End.maxGenEigenspace T μ : Submodule K V) →ₗ[K] K :=
      (Finsupp.lapply
          (⟨μ, k⟩ : (ν : K) ×
            Fin (Module.finrank K (Module.End.maxGenEigenspace T ν : Submodule K V)))).comp
        (((hdec.collectedBasis bμ).repr.toLinearMap).comp
          (Module.End.maxGenEigenspace T μ : Submodule K V).subtype)
    let L2 : (Module.End.maxGenEigenspace T μ : Submodule K V) →ₗ[K] K :=
      (Finsupp.lapply k).comp (bμ μ).repr.toLinearMap
    have hL : L1 = L2 := by
      apply (bμ μ).ext
      intro k'
      simp only [L1, L2, LinearMap.comp_apply, Finsupp.lapply_apply, Submodule.subtype_apply,
        LinearEquiv.coe_coe]
      rw [show ((bμ μ) k' : V) = (hdec.collectedBasis bμ) ⟨μ, k'⟩ from
        (hdec.collectedBasis_coe bμ ▸ rfl)]
      rw [Module.Basis.repr_self_apply, Module.Basis.repr_self_apply]
      simp [Sigma.mk.injEq]
    have := congrArg (fun L => L w) hL
    simpa [L1, L2] using this
  rw [LinearMap.toMatrix_apply, LinearMap.toMatrix_apply, hdec.collectedBasis_coe]
  have hTcoe : T ((bμ μ j : V)) = ((T.restrict (hinv μ)) (bμ μ j) : V) := by
    rw [LinearMap.restrict_apply]
  rw [hTcoe]
  exact hbridge ((T.restrict (hinv μ)) (bμ μ j)) i

theorem collected_repr_off_block_zero
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (bμ : ∀ μ : K, Module.Basis
        (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) K
        (Module.End.maxGenEigenspace T μ : Submodule K V))
    (μ₁ μ₂ : K) (h : μ₁ ≠ μ₂)
    (i : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ₁ : Submodule K V)))
    (y : V) (hy : y ∈ (Module.End.maxGenEigenspace T μ₂ : Submodule K V)) :
    (hdec.collectedBasis bμ).repr y ⟨μ₁, i⟩ = 0  := by
  let L : (Module.End.maxGenEigenspace T μ₂ : Submodule K V) →ₗ[K] K :=
    (Finsupp.lapply
        (⟨μ₁, i⟩ : (ν : K) ×
          Fin (Module.finrank K (Module.End.maxGenEigenspace T ν : Submodule K V)))).comp
      (((hdec.collectedBasis bμ).repr.toLinearMap).comp
        (Module.End.maxGenEigenspace T μ₂ : Submodule K V).subtype)
  have hL : L = 0 := by
    apply (bμ μ₂).ext
    intro k'
    simp only [L, LinearMap.comp_apply, Finsupp.lapply_apply, Submodule.subtype_apply,
      LinearEquiv.coe_coe, LinearMap.zero_apply]
    rw [show ((bμ μ₂) k' : V) = (hdec.collectedBasis bμ) ⟨μ₂, k'⟩ from
      (hdec.collectedBasis_coe bμ ▸ rfl)]
    rw [Module.Basis.repr_self_apply]
    simp [Sigma.mk.injEq, Ne.symm h]
  have hy0 := congrArg (fun f => f ⟨y, hy⟩) hL
  simpa [L] using hy0

-- entry_kind: Builder
-- block_membership: T maps each collectedBasis vector of the μ₂-eigenspace into that eigenspace.
-- Uses collectedBasis_coe to reduce to a subtype element, then applies invariance via hinv.
theorem block_membership
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (bμ : ∀ μ : K, Module.Basis
        (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) K
        (Module.End.maxGenEigenspace T μ : Submodule K V))
    (μ₂ : K)
    (j : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ₂ : Submodule K V))) :
    T ((hdec.collectedBasis bμ) ⟨μ₂, j⟩) ∈
      (Module.End.maxGenEigenspace T μ₂ : Submodule K V) := by
  apply hinv
  rw [hdec.collectedBasis_coe]
  exact (bμ μ₂ j).2

-- Off-diagonal block of `T` in the collected eigenbasis vanishes (μ₁ ≠ μ₂).
-- `block_membership`: `T (collectedBasis ⟨μ₂,j⟩)` stays in the μ₂ generalized eigenspace.
-- `collected_repr_off_block_zero`: the collected-basis coordinate of any vector of the
--   μ₂ summand at a μ₁-index (μ₁ ≠ μ₂) is `0` (direct-sum independence).
-- Combine: unfold the matrix entry via `LinearMap.toMatrix_apply`, then the repr lemma
--   applied to the membership fact closes it.
theorem off_diag
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (bμ : ∀ μ : K, Module.Basis
        (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) K
        (Module.End.maxGenEigenspace T μ : Submodule K V))
    [Fintype ((μ : K) × Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))]
    (μ₁ μ₂ : K) (h : μ₁ ≠ μ₂)
    (i : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ₁ : Submodule K V)))
    (j : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ₂ : Submodule K V))) :
    LinearMap.toMatrix (hdec.collectedBasis bμ) (hdec.collectedBasis bμ) T ⟨μ₁, i⟩ ⟨μ₂, j⟩ = 0  := by
  have hmem : T ((hdec.collectedBasis bμ) ⟨μ₂, j⟩) ∈
      (Module.End.maxGenEigenspace T μ₂ : Submodule K V) :=
    block_membership T hdec hinv bμ μ₂ j
  rw [LinearMap.toMatrix_apply]
  exact collected_repr_off_block_zero T hdec hinv bμ μ₁ μ₂ h i
    (T ((hdec.collectedBasis bμ) ⟨μ₂, j⟩)) hmem

-- Entrywise: matrix of `T` in the collected basis is block-diagonal.
-- `diag_block`: the (μ,μ)-diagonal entry equals the restriction matrix entry.
-- `off_diag`: a (μ₁,μ₂)-entry with μ₁ ≠ μ₂ vanishes (T preserves each summand).
-- Combine via `Matrix.ext` + `by_cases μ₁ = μ₂` and `blockDiagonal'_apply_{eq,ne}`.
theorem collected_matrix_blockdiagonal
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (bμ : ∀ μ : K, Module.Basis
        (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) K
        (Module.End.maxGenEigenspace T μ : Submodule K V))
    [Fintype ((μ : K) × Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))] :
    LinearMap.toMatrix (hdec.collectedBasis bμ) (hdec.collectedBasis bμ) T
      = Matrix.blockDiagonal'
          (fun μ : K => LinearMap.toMatrix (bμ μ) (bμ μ) (T.restrict (hinv μ)))  := by
  apply Matrix.ext
  rintro ⟨μ₁, i⟩ ⟨μ₂, j⟩
  by_cases h : μ₁ = μ₂
  · subst h
    rw [Matrix.blockDiagonal'_apply_eq]
    exact diag_block T hdec hinv bμ μ₁ i j
  · rw [Matrix.blockDiagonal'_apply_ne _ _ _ h]
    exact off_diag T hdec hinv bμ μ₁ μ₂ h i j

-- Entrywise check that the reindexed block-diagonal matrix is Jordan.
-- Off-block entries vanish (`blockDiagonal'_apply_ne`); on-block entries equal the block's
-- entries (`blockDiagonal'_apply_eq`), and `he` transfers the `+1`-adjacency so each block's
-- `IsJordanForm` (`hjor`) closes the per-entry condition.
theorem blockdiag_submatrix_isjordan
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ))
    (e : Fin (Module.finrank K V) ≃ ((μ : K) × Fin (n μ)))
    (he : ∀ p q : Fin (Module.finrank K V), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ)))) :
    IsJordanForm ((Matrix.blockDiagonal' Mμ).submatrix e e)  := by
  intro i j
  by_cases hij : (i : ℕ) = (j : ℕ)
  · rw [if_pos hij]; trivial
  · rw [if_neg hij]
    have hadj := he i j
    have hijne : i ≠ j := fun h => hij (congrArg Fin.val h)
    have hene : e i ≠ e j := fun h => hijne (e.injective h)
    simp only [Matrix.submatrix_apply]
    rcases hei : e i with ⟨μi, ki⟩
    rcases hej : e j with ⟨μj, kj⟩
    rw [hei, hej] at hadj hene
    by_cases hμ : μi = μj
    · subst hμ
      rw [Matrix.blockDiagonal'_apply_eq, Matrix.blockDiagonal'_apply_eq,
        Matrix.blockDiagonal'_apply_eq]
      have hkne : ki ≠ kj := fun h => hene (by rw [h])
      have hkv : (ki : ℕ) ≠ (kj : ℕ) := fun h => hkne (Fin.val_injective h)
      have hb := hjor μi ki kj
      rw [if_neg hkv] at hb
      have hiff := hadj rfl
      split_ifs with hij1
      · rw [if_pos (hiff.mpr hij1)] at hb; exact hb
      · rw [if_neg (fun h => hij1 (hiff.mp h))] at hb; exact hb
    · rw [Matrix.blockDiagonal'_apply_ne Mμ ki kj hμ]
      split_ifs <;> simp

-- reindex_tomatrix_eq_blockdiag_submatrix: reindexing a block-diagonal basis by e gives
-- (blockDiagonal' Mμ).submatrix e e, via Basis.reindex repr/apply bookkeeping.
-- entry_kind: Builder
theorem reindex_tomatrix_eq_blockdiag_submatrix
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ))
    (e : Fin (Module.finrank K V) ≃ ((μ : K) × Fin (n μ)))
    (he : ∀ p q : Fin (Module.finrank K V), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ)))) :
    LinearMap.toMatrix (b.reindex e.symm) (b.reindex e.symm) T
      = (Matrix.blockDiagonal' Mμ).submatrix e e := by
  rw [← hb]
  ext i j
  simp only [Matrix.submatrix_apply, LinearMap.toMatrix_apply]
  rw [Module.Basis.reindex_apply]
  have hrepr : ∀ (v : V), (b.reindex e.symm).repr v i = b.repr v (e i) := fun v => by
    simp [Module.Basis.reindex, Finsupp.domLCongr_apply]
  rw [hrepr, Equiv.symm_symm]

-- Reindex the block-diagonal basis `b` by the order-iso `e` to a `Fin (finrank V)` basis.
-- `reindex_tomatrix_eq_blockdiag_submatrix`: the reindexed basis' matrix equals
--   `(blockDiagonal' Mμ).submatrix e e` (pure `toMatrix`/`reindex` bookkeeping).
-- `blockdiag_submatrix_isjordan`: that submatrix is Jordan form — block-wise from `hjor` and the
--   consecutive-index order property `he` (pure matrix combinatorics, no `T`/basis).
-- Combine: rewrite the goal matrix to the submatrix, then apply the Jordan-form fact.
theorem reindex_blockdiag_to_jordan
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ))
    (e : Fin (Module.finrank K V) ≃ ((μ : K) × Fin (n μ)))
    (he : ∀ p q : Fin (Module.finrank K V), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ)))) :
    ∃ b' : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b' b' T) := by
  refine ⟨b.reindex e.symm, ?_⟩
  have h1 := reindex_tomatrix_eq_blockdiag_submatrix T b Mμ hb hjor e he
  rw [h1]
  exact blockdiag_submatrix_isjordan T b Mμ hb hjor e he

-- Reindex a block-diagonal (per-block Jordan) basis to a `Fin (finrank V)` global Jordan basis.
-- `jordan_block_enumeration`: there is an enumeration `e : Fin (finrank V) ≃ Σ μ, Fin (n μ)` laying
--   the blocks out contiguously and in-order — i.e. within a block, `Fin`-positions are consecutive
--   iff the within-block indices are (the order-isomorphism property `he`).
-- `reindex_blockdiag_to_jordan`: given such an `e`, the reindexed basis `b.reindex e.symm` has matrix
--   `blockDiagonal' Mμ ∘ e`, whose Jordan form follows from `hjor` block-wise plus `he`.
-- First sub-goal is pure index combinatorics on the sigma fintype (no T / matrices in its content);
-- second is matrix bookkeeping (`toMatrix_reindex` + `blockDiagonal'_apply` + case split).
theorem block_diagonal_reindex_jordan
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ)) :
    ∃ b' : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b' b' T)  := by
  obtain ⟨e, he⟩ := jordan_block_enumeration T b Mμ hb hjor
  exact reindex_blockdiag_to_jordan T b Mμ hb hjor e he

-- Glue the per-eigenspace Jordan bases into a global Jordan-form basis (Brick C step 4).
-- `collected_matrix_blockdiagonal`: over the collected basis of the internal direct sum
--   `hdec`, the matrix of `T` is block-diagonal with diagonal blocks the per-eigenspace
--   restriction matrices `toMatrix (bμ μ) (bμ μ) (T.restrict (hinv μ))`.
-- `block_diagonal_reindex_jordan`: any basis whose matrix is block-diagonal with each diagonal
--   block already in Jordan form reindexes (blocks laid out contiguously) to a
--   `Fin (finrank V)` basis in global Jordan form.
-- Each sub-goal drops a layer: the first is direct-sum / restriction bookkeeping, the second
-- is pure matrix combinatorics (no eigenspaces, no invariance).
theorem glue_maxgen_jordan_blocks
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

end Library.LinearAlgebra.JordanForm.BlockDiagonal
