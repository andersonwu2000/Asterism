import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct proof (leaf-bypass): `Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))`
-- is a monoid hom `FreeGroup (Fin 2) →* ℝ`; show it is ≡ 1 by free-group induction
-- (generators have det 1 via hdetA/hdetB; closed under one/mul/inv), then transport
-- the value back to `LinearMap.det` of the lift via hmatdet.
theorem s11485
    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (hmatdet : ∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap))
    (hdetA : (mat (g 0)).det = 1) (hdetB : (mat (g 1)).det = 1)
    (w : FreeGroup (Fin 2)) :
    LinearMap.det ((FreeGroup.lift g w).toLinearEquiv.toLinearMap) = 1  := by
  have key : ∀ v : FreeGroup (Fin 2),
      (Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))) v = 1 := by
    intro v
    induction v using FreeGroup.induction_on with
    | C1 => simp
    | of x => fin_cases x <;> simp [hdetA, hdetB]
    | inv_of x ih =>
        have h2 := (Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))).map_mul
          (FreeGroup.of x)⁻¹ (FreeGroup.of x)
        simp only [inv_mul_cancel, map_one, ih, mul_one] at h2
        exact h2.symm
    | mul x y ihx ihy => rw [map_mul, ihx, ihy, mul_one]
  rw [← hmatdet]
  exact key w

end Problems.Geometry.banach_tarski
