import Mathlib
import Problems.Minif2f.amc12a_2003_p25.Defs

namespace Problems.Minif2f.amc12a_2003_p25

-- Direct: hypothesis `0 ≤ f x` is vacuous since `Real.sqrt _ ≥ 0`, so the LHS set is `univ`.
-- Then `h₂` makes `f` surjective, contradicting `f x = sqrt _ ≥ 0` at the value `-1`.
-- The sign hypothesis `0 < a` is unused — h₀, h₁, h₂ alone are inconsistent.
theorem s780 : ∀ (a b : ℝ) (f : ℝ → ℝ), 0 < b → (∀ x, f x = Real.sqrt (a * x ^ 2 + b * x)) → { x | 0 ≤ f x } = f '' { x | 0 ≤ f x } → 0 < a → False  := by
  intro a b f h₀ h₁ h₂ ha
  have hS : {x | 0 ≤ f x} = Set.univ := by
    ext x
    simp [h₁ x, Real.sqrt_nonneg]
  rw [hS] at h₂
  have h_neg1 : (-1 : ℝ) ∈ (Set.univ : Set ℝ) := Set.mem_univ _
  rw [h₂] at h_neg1
  obtain ⟨x, _, hx⟩ := h_neg1
  have hf_nn : 0 ≤ f x := by rw [h₁]; exact Real.sqrt_nonneg _
  linarith

end Problems.Minif2f.amc12a_2003_p25
