import Mathlib
import Problems.pi1_circle.Defs

namespace Problems.pi1_circle

open Real

-- winding_quot_refl_zero: the lift of the constant loop at 1 is constant at 0,
-- so h_char gives 0 = W'⟦refl⟧ * 2π, whence W'⟦refl⟧ = 0.
theorem winding_quot_refl_zero
    (W' : Path.Homotopic.Quotient (1 : Circle) 1 → ℤ)
    (h_char : ∀ (γ : Path (1 : Circle) 1),
        Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
            (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = (W' ⟦γ⟧ : ℝ) * (2 * π)) :
    W' (⟦Path.refl (1 : Circle)⟧ : Path.Homotopic.Quotient (1 : Circle) 1) = 0 := by
  have h0 := h_char (Path.refl 1)
  have hlift : Circle.isCoveringMap_exp.liftPath (Path.refl (1 : Circle)).toContinuousMap 0
      (by simp : (Path.refl (1 : Circle)).toContinuousMap 0 = Circle.exp 0) 1 = 0 := by
    have heq : ContinuousMap.const (↑unitInterval) (0 : ℝ) =
        Circle.isCoveringMap_exp.liftPath (Path.refl (1 : Circle)).toContinuousMap 0
        (by simp) := by
      rw [IsCoveringMap.eq_liftPath_iff']
      exact ⟨by ext t; simp [Circle.exp_zero, Path.refl], by simp⟩
    simpa using DFunLike.congr_fun heq.symm (⟨1, by norm_num⟩ : unitInterval)
  rw [hlift] at h0
  have h1 : (W' ⟦Path.refl (1 : Circle)⟧ : ℝ) = 0 := by
    nlinarith [pi_pos, h0]
  exact_mod_cast h1

end Problems.pi1_circle
