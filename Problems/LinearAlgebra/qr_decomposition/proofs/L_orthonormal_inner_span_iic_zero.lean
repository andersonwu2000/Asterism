import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs

namespace Problems.LinearAlgebra.qr_decomposition

-- orthonormal_inner_span_iic_zero: q i is orthogonal to span(q '' Set.Iic j) when j < i.
-- Proves q i ∈ (span ℝ (q '' Set.Iic j))ᗮ via span_induction; each generator q k has k ≤ j < i
-- so k ≠ i, giving inner ℝ (q k) (q i) = 0 by orthonormality; bilinearity extends to the span.
-- entry_kind: Builder
theorem orthonormal_inner_span_iic_zero {n : ℕ}
    (q : Fin n → EuclideanSpace ℝ (Fin n))
    (i j : Fin n)
    (v : EuclideanSpace ℝ (Fin n)) :
    Orthonormal ℝ q →
    v ∈ Submodule.span ℝ (q '' Set.Iic j) →
    j < i →
    inner (𝕜 := ℝ) (q i) v = 0 := by
  intro hq hv hij
  have hmem : q i ∈ (Submodule.span ℝ (q '' Set.Iic j))ᗮ := by
    rw [Submodule.mem_orthogonal]
    intro x hx
    induction hx using Submodule.span_induction with
    | mem y hy =>
      obtain ⟨k, hk, rfl⟩ := hy
      simp only [Set.mem_Iic] at hk
      apply hq.2
      intro h
      rw [h] at hk
      exact absurd (hk.trans_lt hij) (lt_irrefl _)
    | zero => simp
    | add a b _ _ iha ihb => rw [inner_add_left]; linarith
    | smul c a _ iha => simp [inner_smul_left, iha]
  have hvi := hmem v hv
  rwa [real_inner_comm] at hvi

end Problems.LinearAlgebra.qr_decomposition
