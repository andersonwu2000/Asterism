import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_combo_zero_set_eq_cos_shift
import Problems.Geometry.banach_tarski.proofs.L_cos_shift_set_eq_image

namespace Problems.Geometry.banach_tarski

-- Amplitude-phase: rewrite the level set through cos(φ+ψ), then transport by shift.
-- h1: cos φ·a − sin φ·b = √(a²+b²)·cos(φ+ψ) and √(a²+b²)≠0 collapse the LHS zero set
--     to {cos(φ+ψ)=0} (uses ha, hb, h);
-- h2: the pure shift identity {cos(φ+ψ)=0} = (·−ψ)''{cosθ=0} (no a,b dependence);
-- transitivity closes the parent — each sub-goal is a single, smaller set equality.
theorem s11452 (a b ψ : ℝ) (h : a ≠ 0 ∨ b ≠ 0)
    (ha : a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ)
    (hb : b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0} =
      (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0}  := by
  have h1 : {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}
      = {φ : ℝ | Real.cos (φ + ψ) = 0} :=
    combo_zero_set_eq_cos_shift a b ψ h ha hb
  have h2 : {φ : ℝ | Real.cos (φ + ψ) = 0}
      = (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0} :=
    cos_shift_set_eq_image ψ
  exact h1.trans h2
end Problems.Geometry.banach_tarski
