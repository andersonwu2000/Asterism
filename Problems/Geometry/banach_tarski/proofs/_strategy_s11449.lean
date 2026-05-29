import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_combo_zero_eq_cos_zero_shift
import Problems.Geometry.banach_tarski.proofs.L_cos_zero_set_countable

namespace Problems.Geometry.banach_tarski

-- Amplitude-phase reduction: a·cosφ − b·sinφ = r·cos(φ+ψ) (r≠0), so its zero set is the
-- cos-zero set {(2n+1)π/2} translated by −ψ. Two sub-goals:
--   cos_zero_set_countable      — the cos-zero set is countable (range over ℤ);
--   combo_zero_eq_cos_zero_shift — the parent zero set equals that set shifted by −ψ.
-- Countable image of a countable set closes the parent.
theorem s11449 (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}.Countable  := by
  have hcos := cos_zero_set_countable
  obtain ⟨ψ, hψ⟩ := combo_zero_eq_cos_zero_shift a b h
  rw [hψ]
  exact hcos.image _

end Problems.Geometry.banach_tarski
