import Mathlib
import Problems.pi1_circle.Defs

namespace Problems.pi1_circle

open Real

-- standard_loop_data: constructs the standard n-fold loop on Circle with its real lift Γ_n
-- Γ_n t = t * n * (2π) lifts to Circle.exp ∘ Γ_n, a loop from 1 to 1.
theorem standard_loop_data
    (W' : Path.Homotopic.Quotient (1 : Circle) 1 → ℤ)
    (h_char : ∀ (γ : Path (1 : Circle) 1),
        Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
            (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = (W' ⟦γ⟧ : ℝ) * (2 * π))
    (n : ℤ) :
    ∃ (γ : Path (1 : Circle) 1) (Γ : C(unitInterval, ℝ)),
      Γ 0 = 0 ∧ (Γ 1 : ℝ) = (n : ℝ) * (2 * π) ∧
      Circle.exp ∘ (Γ : unitInterval → ℝ) = γ.toContinuousMap := by
  let Γ : C(unitInterval, ℝ) := ⟨fun t => (t : ℝ) * (n : ℝ) * (2 * π), by continuity⟩
  have hΓ0 : (Γ 0 : ℝ) = 0 := by simp [Γ]
  have hΓ1 : (Γ 1 : ℝ) = (n : ℝ) * (2 * π) := by simp [Γ]
  have h_src : Circle.exp (Γ 0) = 1 := by rw [hΓ0]; exact Circle.exp_zero
  have h_tgt : Circle.exp (Γ 1) = 1 := by
    rw [hΓ1]; exact Circle.exp_int_mul_two_pi n
  let γ : Path (1 : Circle) 1 :=
    { toContinuousMap := Circle.exp.comp Γ
      source' := h_src
      target' := h_tgt }
  exact ⟨γ, Γ, hΓ0, hΓ1, rfl⟩

end Problems.pi1_circle

