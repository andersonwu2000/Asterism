import Mathlib
import Problems.Minif2f.mathd_algebra_149.Defs
import Problems.Minif2f.mathd_algebra_149.proofs.L_preimage_eq_singleton

namespace Problems.Minif2f.mathd_algebra_149

-- Reduce the sum to a singleton: prove `f ⁻¹' {10} = {6}` (sub-goal), then
-- the toFinset is `{6}` by congruence, and `Finset.sum_singleton` closes the sum.
theorem s640 : ∀ (f : ℝ → ℝ) (h₀ : ∀ x < -5, f x = x ^ 2 + 5) (h₁ : ∀ x ≥ -5, f x = 3 * x - 8) (h₂ : Fintype (f ⁻¹' {10})), (∑ k ∈ (f ⁻¹' {10}).toFinset, k) = 6  := by
  intro f h₀ h₁ h₂
  have h_preimage : f ⁻¹' {10} = ({6} : Set ℝ) := preimage_eq_singleton f h₀ h₁
  have h_finset : (f ⁻¹' {10}).toFinset = ({6} : Finset ℝ) := by
    ext x
    simp [h_preimage]
  rw [h_finset]
  simp

end Problems.Minif2f.mathd_algebra_149
