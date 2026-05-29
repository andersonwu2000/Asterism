import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_amplitude_phase_exists
import Problems.Geometry.banach_tarski.proofs.L_combo_zero_set_eq

namespace Problems.Geometry.banach_tarski

-- Amplitude-phase reduction: choose ψ with a = r·cosψ, b = r·sinψ (r = √(a²+b²) ≠ 0),
-- so cosφ·a − sinφ·b = r·cos(φ+ψ); its zero set is {cos(φ+ψ)=0} = (·−ψ)''{cosθ=0}.
--   amplitude_phase_exists  — the phase witness ψ (via Complex.arg of a+b·I);
--   combo_zero_set_eq       — the set equality given that phase data.
theorem s11450 (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    ∃ ψ : ℝ, {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0} =
      (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0}  := by
  obtain ⟨ψ, ha, hb⟩ := amplitude_phase_exists a b h
  exact ⟨ψ, combo_zero_set_eq a b ψ h ha hb⟩

end Problems.Geometry.banach_tarski
