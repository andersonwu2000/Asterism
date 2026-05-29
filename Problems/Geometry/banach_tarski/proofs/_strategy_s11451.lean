import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Amplitude-phase witness via the complex argument: take ψ = arg ⟨a,b⟩.
-- Then cos ψ = re/‖z‖ = a/√(a²+b²) and sin ψ = im/‖z‖ = b/√(a²+b²); since
-- a≠0∨b≠0 gives ‖z‖=√(a²+b²)≠0, multiplying back cancels. Direct, no sub-goals.
theorem s11451 (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    ∃ ψ : ℝ, a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ ∧
      b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ := by
  have hz0 : (⟨a, b⟩ : ℂ) ≠ 0 := by
    simp only [ne_eq, Complex.ext_iff, Complex.zero_re, Complex.zero_im, not_and]
    rcases h with ha | hb <;> intro <;> simp_all
  have hnorm : ‖(⟨a, b⟩ : ℂ)‖ = Real.sqrt (a ^ 2 + b ^ 2) := by
    rw [Complex.norm_def, Complex.normSq_mk]; ring_nf
  refine ⟨Complex.arg ⟨a, b⟩, ?_, ?_⟩
  · rw [Complex.cos_arg hz0, hnorm]
    have : (⟨a, b⟩ : ℂ).re = a := rfl
    rw [this, mul_div_cancel₀]
    rw [ne_eq, ← hnorm]
    simpa using hz0
  · rw [Complex.sin_arg, hnorm]
    have : (⟨a, b⟩ : ℂ).im = b := rfl
    rw [this, mul_div_cancel₀]
    rw [ne_eq, ← hnorm]
    simpa using hz0

end Problems.Geometry.banach_tarski
