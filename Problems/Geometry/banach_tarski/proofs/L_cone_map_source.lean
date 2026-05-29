import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- cone_map_source: radial cone image lands in cone of target (uses map_source + ‖x‖=1 on sphere)
-- If y = r•x with x ∈ e.source ⊆ sphere and r ∈ (0,1], then ‖y‖=r, ‖y‖⁻¹•y = x, so
-- ‖y‖•e(‖y‖⁻¹•y) = r•e(x) ∈ cone of e.target by e.map_source.
theorem cone_map_source (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} →
      ‖y‖ • e.toFun (‖y‖⁻¹ • y) ∈
        {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} := by
  intro y hy
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  have hxnorm : ‖x‖ = 1 := by
    have h := hsrc hx
    simp only [Metric.mem_sphere, dist_zero_right] at h
    exact h
  have hrnorm : ‖r • x‖ = r := by
    rw [norm_smul, Real.norm_of_nonneg (le_of_lt hr.1), hxnorm, mul_one]
  have hinv : r⁻¹ • r • x = x := inv_smul_smul₀ (ne_of_gt hr.1) x
  rw [hrnorm, hinv]
  exact ⟨r, hr, e.toFun x, e.map_source hx, rfl⟩
end Problems.Geometry.banach_tarski
