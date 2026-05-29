import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

open Matrix

-- Build `mat` as the standard-basis matrix functor on the underlying linear maps:
--   mat T := LinearMap.toMatrix b b T.toLinearEquiv.toLinearMap,   b = (EuclideanSpace.basisFun …).toBasis.
-- The MonoidHom laws come from the End↔Matrix linear functor: `T ↦ T.toLinearEquiv.toLinearMap`
-- carries 1↦1 and (T₁*T₂)↦(·)*(·) (both `ext x; rfl`), then `LinearMap.toMatrix_one`/`toMatrix_mul`.
-- Injectivity: `LinearMap.toMatrix b b` is a LinearEquiv (injective) precomposed with the injective
--   coercions `LinearEquiv.toLinearMap_injective`/`LinearIsometryEquiv.toLinearEquiv_injective`.
-- det compatibility: `LinearMap.det_toMatrix`. Computation rule: `(LinearMap.toMatrix b b).symm`
--   is defeq `Matrix.toEuclideanLin`, so `LinearEquiv.eq_symm_apply … |>.mp rfl` reads off the matrix.
-- Sorry-free; ships as a leaf.
theorem s11491 :
    ∃ mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ,
      Function.Injective mat ∧
      (∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap)) ∧
      (∀ (T : E ≃ₗᵢ[ℝ] E) (M : Matrix (Fin 3) (Fin 3) ℝ),
          (∀ x : E, T x = Matrix.toEuclideanLin M x) → mat T = M)  := by
  set b := (EuclideanSpace.basisFun (Fin 3) ℝ).toBasis with hb
  refine ⟨{
    toFun := fun T => LinearMap.toMatrix b b T.toLinearEquiv.toLinearMap
    map_one' := by
      have : ((1 : E ≃ₗᵢ[ℝ] E).toLinearEquiv.toLinearMap) = 1 := by ext x; rfl
      rw [this, LinearMap.toMatrix_one]
    map_mul' := by
      intro T₁ T₂
      have : ((T₁ * T₂).toLinearEquiv.toLinearMap)
          = (T₁.toLinearEquiv.toLinearMap) * (T₂.toLinearEquiv.toLinearMap) := by ext x; rfl
      rw [this, LinearMap.toMatrix_mul]
  }, ?_, ?_, ?_⟩
  · intro T₁ T₂ h
    simp only [MonoidHom.coe_mk, OneHom.coe_mk] at h
    have h2 : (T₁.toLinearEquiv.toLinearMap) = (T₂.toLinearEquiv.toLinearMap) :=
      (LinearMap.toMatrix b b).injective h
    have h3 : T₁.toLinearEquiv = T₂.toLinearEquiv := LinearEquiv.toLinearMap_injective h2
    exact LinearIsometryEquiv.toLinearEquiv_injective h3
  · intro T
    simp only [MonoidHom.coe_mk, OneHom.coe_mk]
    exact LinearMap.det_toMatrix b _
  · intro T M hTM
    simp only [MonoidHom.coe_mk, OneHom.coe_mk]
    have : T.toLinearEquiv.toLinearMap = Matrix.toEuclideanLin M :=
      LinearMap.ext fun x => hTM x
    rw [this]
    exact (LinearEquiv.eq_symm_apply (LinearMap.toMatrix b b)).mp rfl

end Problems.Geometry.banach_tarski
