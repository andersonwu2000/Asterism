import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_rotation_fixed_set_on_sphere_finite

namespace Problems.Geometry.banach_tarski

-- The radius-1/2 fixed set is the image of the radius-1 fixed set under x ↦ (1/2)•x.
-- Scale half→full by x ↦ 2•x: it injects the half-sphere fixed set into the radius-1
-- fixed set (proved finite as rotation_fixed_set_on_sphere_finite), so finiteness pulls back.
theorem s11520 : ∀ (R : E ≃ₗᵢ[ℝ] E),
    LinearMap.det (R.toLinearEquiv.toLinearMap) = 1 → R ≠ LinearIsometryEquiv.refl ℝ E →
    {x ∈ Metric.sphere (0 : E) (1 / 2) | R x = x}.Finite  := by
  intro R hdet hT
  have hfull := rotation_fixed_set_on_sphere_finite R hdet hT
  apply Set.Finite.of_finite_image (f := fun x => (2 : ℝ) • x)
  · apply hfull.subset
    rintro y ⟨x, ⟨hx_sph, hx_fix⟩, rfl⟩
    simp only [Set.mem_setOf_eq, Metric.mem_sphere, dist_eq_norm, sub_zero] at hx_sph ⊢
    refine ⟨?_, ?_⟩
    · rw [norm_smul, Real.norm_eq_abs, hx_sph]; norm_num
    · rw [map_smul, hx_fix]
  · intro a _ b _ hab
    exact smul_right_injective E (by norm_num) hab

end Problems.Geometry.banach_tarski
