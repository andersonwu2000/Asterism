import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_standard_loop_data

namespace Problems.pi1_circle

open Real

-- Construct the standard loop γ_n with companion real lift Γ_n satisfying
-- `Circle.exp ∘ Γ_n = γ_n.toContinuousMap`, `Γ_n 0 = 0`, `Γ_n 1 = n*(2π)`.
-- The canonical lift then equals Γ_n by `eq_liftPath_iff'`, giving the
-- endpoint conclusion immediately.
theorem s10698
    (W' : Path.Homotopic.Quotient (1 : Circle) 1 → ℤ)
    (h_char : ∀ (γ : Path (1 : Circle) 1),
        Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
            (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = (W' ⟦γ⟧ : ℝ) * (2 * π))
    (n : ℤ) :
    ∃ (γ : Path (1 : Circle) 1),
        Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
          (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = (n : ℝ) * (2 * π)  := by
  have h_data := standard_loop_data W' h_char n

  obtain ⟨γ, Γ, hΓ0, hΓ1, hlifts⟩ := h_data
  refine ⟨γ, ?_⟩
  have h_eq : Γ = Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
      (by simp : γ.toContinuousMap 0 = Circle.exp 0) :=
    (Circle.isCoveringMap_exp.eq_liftPath_iff'
      (by simp : γ.toContinuousMap 0 = Circle.exp 0)).mpr ⟨hlifts, hΓ0⟩
  have h1 : Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
      (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = Γ 1 := by
    rw [← h_eq]
  rw [h1]; exact hΓ1




end Problems.pi1_circle
