import Mathlib
import Problems.Minif2f.amc12a_2003_p25.Defs

namespace Problems.Minif2f.amc12a_2003_p25

-- Direct proof: hypotheses h₁ ∧ h₂ are inconsistent (independent of a's sign).
-- f x = Real.sqrt _ ≥ 0 always, so {x | 0 ≤ f x} = univ; h₂ then forces
-- -1 ∈ f '' univ, contradicting Real.sqrt_nonneg. From False, a = -4 follows.
theorem s9257 : ∀ (a b : ℝ) (f : ℝ → ℝ), 0 < b → (∀ x, f x = Real.sqrt (a * x ^ 2 + b * x)) → { x | 0 ≤ f x } = f '' { x | 0 ≤ f x } → a < 0 → a = -4  := by
  intro a b f h₀ h₁ h₂ _
  have h_univ : {x | (0:ℝ) ≤ f x} = Set.univ := by
    ext x; simp [h₁ x, Real.sqrt_nonneg]
  rw [h_univ] at h₂
  have h_neg : (-1 : ℝ) ∈ f '' Set.univ := h₂ ▸ Set.mem_univ _
  obtain ⟨y, _, hy⟩ := h_neg
  have hge : (0 : ℝ) ≤ f y := h₁ y ▸ Real.sqrt_nonneg _
  linarith

end Problems.Minif2f.amc12a_2003_p25
