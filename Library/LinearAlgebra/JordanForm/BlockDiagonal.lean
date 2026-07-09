import Library.LinearAlgebra.JordanForm.BlockEnum
import Library.LinearAlgebra.JordanForm.Defs
import Mathlib

/-!
# Block-diagonal structure of T in the collected eigenbasis

This file establishes that the matrix of a linear endomorphism `T` in the basis collected from
per-eigenspace bases is block-diagonal, with diagonal blocks equal to the restrictions of `T` to
the generalized eigenspaces. It then reindexes this block-diagonal structure to produce a global
`Fin (finrank K V)`-indexed basis in Jordan normal form, given that each restriction block is
already in Jordan form.
-/

open Library.LinearAlgebra.JordanForm.BlockEnum
open Library.LinearAlgebra.JordanForm.Defs

namespace Library.LinearAlgebra.JordanForm.BlockDiagonal

variable {K : Type*} [Field K] [DecidableEq K]
variable {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
variable (T : V →ₗ[K] V)

/-- The `(μ, i), (μ, j)` entry of the matrix of `T` in the collected basis equals the `(i, j)`
entry of the matrix of the restriction `T.restrict (hinv μ)` in the basis `bμ μ`. -/
theorem diag_block
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

/-- The `(μ₁, i)`-coordinate of the collected-basis representation of any vector in the
`μ₂`-generalized eigenspace is zero when `μ₁ ≠ μ₂`, reflecting direct-sum independence. -/
theorem collected_repr_off_block_zero
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

-- block_membership: T maps each collectedBasis vector of the μ₂-eigenspace into that eigenspace.
-- Uses collectedBasis_coe to reduce to a subtype element, then applies invariance via hinv.
theorem block_membership
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
      (Module.End.maxGenEigenspace T μ₂ : Submodule K V) := hinv μ₂ _ (hdec.collectedBasis_mem bμ ⟨μ₂, j⟩)

/-- The `(μ₁, i), (μ₂, j)` entry of the matrix of `T` in the collected basis is zero when
`μ₁ ≠ μ₂`, because `T` preserves each generalized eigenspace and the summands are independent. -/
theorem off_diag
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

/-- The matrix of `T` in the collected basis of the internal direct sum `hdec` equals the block-diagonal
matrix whose `μ`-th block is the matrix of the restriction `T.restrict (hinv μ)` in the basis `bμ μ`. -/
theorem collected_matrix_blockdiagonal
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

section BlockReindex

variable {n : K → ℕ} [Fintype ((μ : K) × Fin (n μ))]
variable (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
variable (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)

/-- If `b`'s matrix is block-diagonal with per-block Jordan form, and `e` is an order-compatible
enumeration of the sigma type, then the submatrix `(blockDiagonal' Mμ).submatrix e e` is in Jordan
form. -/
theorem blockdiag_submatrix_isjordan
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

/-- The matrix of `T` in the reindexed basis `b.reindex e.symm` equals the submatrix
`(blockDiagonal' Mμ).submatrix e e`, via `Basis.reindex` representation bookkeeping. -/
theorem reindex_tomatrix_eq_blockdiag_submatrix
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

/-- Given an order-compatible enumeration `e`, the reindexed basis `b.reindex e.symm` is a
`Fin (finrank K V)`-indexed basis for `V` whose matrix is in Jordan normal form. -/
theorem reindex_blockdiag_to_jordan
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

/-- If the matrix of `T` in `b` is block-diagonal with each block in Jordan form, there exists a
`Fin (finrank K V)`-indexed global Jordan-form basis, obtained by enumerating the block structure
contiguously via `jordan_block_enumeration`. -/
theorem block_diagonal_reindex_jordan
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ)) :
    ∃ b' : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b' b' T)  := by
  obtain ⟨e, he⟩ := jordan_block_enumeration T b Mμ hb hjor
  exact reindex_blockdiag_to_jordan T b Mμ hb hjor e he

end BlockReindex

/-- Given an internal direct-sum decomposition into generalized eigenspaces and per-eigenspace
Jordan bases, there exists a global `Fin (finrank K V)`-indexed basis for `V` in Jordan normal form. -/
theorem glue_maxgen_jordan_blocks
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
