import Library.LinearAlgebra.LeadingPrincipalMinor
import Mathlib

/-!
# Block structure for the Sylvester criterion

This file establishes block-decomposition lemmas for a real Hermitian matrix `M` of size
`(n + 1) × (n + 1)`, reindexed via `finSumFinEquiv`, that are used to run an inductive
step in the Sylvester positivity criterion. It shows that the off-diagonal block `toBlocks₂₁`
equals the conjugate transpose of `toBlocks₁₂`, that the top-left block `toBlocks₁₁` is
Hermitian, and that positivity of all leading principal minors of `M` descends to the
top-left `n × n` block.
-/

open Library.LinearAlgebra.LeadingPrincipalMinor

namespace Library.LinearAlgebra.LeadingPrincipalMinorBlock

variable {n : ℕ} (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)

/-- The lower-left block `toBlocks₂₁` of a Hermitian matrix, after reindexing via
`finSumFinEquiv`, equals the conjugate transpose of the upper-right block `toBlocks₁₂`. -/
theorem block_conjtranspose
    (hHerm : M.IsHermitian) :
    (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₁
      = (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose := by
  have hSub : (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).IsHermitian :=
    hHerm.submatrix _
  ext i j
  simp only [Matrix.toBlocks₂₁, Matrix.toBlocks₁₂, Matrix.conjTranspose, Matrix.transpose,
             Matrix.submatrix]
  exact congr_fun (congr_fun hSub (Sum.inl j)) (Sum.inr i)

/-- The top-left block `toBlocks₁₁` of a Hermitian matrix, after reindexing via
`finSumFinEquiv`, is itself Hermitian. -/
theorem block_hermitian (hHerm : M.IsHermitian) :
    (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.IsHermitian := by
  simp only [Matrix.toBlocks₁₁]
  exact Matrix.IsHermitian.submatrix hHerm (↑finSumFinEquiv ∘ Sum.inl)

/-- If every leading principal minor of `M` is positive, then every leading principal minor of
the top-left `n × n` block (the `toBlocks₁₁` piece of the reindexed `M`) is also positive.
Each block minor at index `k` coincides with the leading minor of `M` at `k.castSucc`. -/
theorem block_minors_pos
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    ∀ (k : Fin n), 0 < leadingPrincipalMinor
      (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ k := by
  intro k
  have h_minor_eq : leadingPrincipalMinor
      (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ k
      = leadingPrincipalMinor M k.castSucc := by
    simp only [leadingPrincipalMinor, Matrix.toBlocks₁₁]
    congr 1
  rw [h_minor_eq]
  exact hMinors k.castSucc

end Library.LinearAlgebra.LeadingPrincipalMinorBlock
