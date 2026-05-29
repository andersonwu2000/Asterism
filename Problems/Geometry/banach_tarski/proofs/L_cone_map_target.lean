import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- cone_map_target: radial cone image lands in the cone of e.source via e.invFun + norm algebra
-- y = r•x (x ∈ e.target, r ∈ (0,1]); ‖y‖ = r (since x on unit sphere); ‖y‖⁻¹•y = x;
-- e.invFun x ∈ e.source; conclusion r • e.invFun x in cone of e.source.
-- entry_kind: Builder
theorem cone_map_target (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} →
      ‖y‖ • e.invFun (‖y‖⁻¹ • y) ∈
        {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} := by
    intro y hy
    simp only [Set.mem_setOf_eq] at hy ⊢
    obtain ⟨r, hr, x, hx, rfl⟩ := hy
    have hxs : x ∈ Metric.sphere (0 : E) 1 := htgt hx
    have hxnorm : ‖x‖ = 1 := by rwa [Metric.mem_sphere, dist_zero_right] at hxs
    have hrpos : (0 : ℝ) < r := hr.1
    have hnorm : ‖r • x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hrpos.le, hxnorm, mul_one]
    have hef : e.invFun x ∈ e.source := e.map_target' hx
    exact ⟨r, hr, e.invFun x, hef, by rw [hnorm]; congr 1; rw [inv_smul_smul₀ hrpos.ne']⟩

end Problems.Geometry.banach_tarski