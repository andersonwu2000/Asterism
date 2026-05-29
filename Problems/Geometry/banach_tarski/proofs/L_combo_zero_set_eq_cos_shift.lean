import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- combo_zero_set_eq_cos_shift: amplitude-phase identity; cos φ·a − sin φ·b = √(a²+b²)·cos(φ+ψ),
-- so the zero set equals {cos(φ+ψ)=0} after cancelling the nonzero amplitude.
-- entry_kind: Builder
theorem combo_zero_set_eq_cos_shift (a b ψ : ℝ) (h : a ≠ 0 ∨ b ≠ 0)
    (ha : a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ)
    (hb : b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}
      = {φ : ℝ | Real.cos (φ + ψ) = 0} := by
  have hsqrt : Real.sqrt (a ^ 2 + b ^ 2) ≠ 0 := by
    intro h0
    have hle : a ^ 2 + b ^ 2 ≤ 0 :=
      Real.sqrt_eq_zero'.mp
        (le_antisymm (by linarith [Real.sqrt_nonneg (a ^ 2 + b ^ 2)]) (Real.sqrt_nonneg _))
    have ha0 : a = 0 := by nlinarith [sq_nonneg a, sq_nonneg b]
    have hb0 : b = 0 := by nlinarith [sq_nonneg a, sq_nonneg b]
    exact h.elim (· ha0) (· hb0)
  have hkey : ∀ φ : ℝ, Real.cos φ * a - Real.sin φ * b =
      Real.sqrt (a ^ 2 + b ^ 2) * Real.cos (φ + ψ) := fun φ => by
    rw [Real.cos_add]
    linear_combination Real.cos φ * ha - Real.sin φ * hb
  ext φ
  simp only [Set.mem_setOf_eq, hkey φ]
  constructor
  · intro heq; exact (mul_eq_zero.mp heq).resolve_left hsqrt
  · intro heq; exact mul_eq_zero.mpr (Or.inr heq)

end Problems.Geometry.banach_tarski
