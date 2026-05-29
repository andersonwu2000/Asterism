import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- cone_left_inv: radial-lift left-inverse via sphere norm = 1 and PartialEquiv.left_inv'
-- For y = r•x with x on the unit sphere (e.source), normalize by ‖y‖=r, apply e then e.invFun.
theorem cone_left_inv (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} →
      (fun z => ‖z‖ • e.invFun (‖z‖⁻¹ • z))
        ((fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z)) y) = y := by
    intro y hy
    obtain ⟨r, hr, x, hx, rfl⟩ := hy
    simp only []
    have hxnorm : ‖x‖ = 1 := by
      have := hsrc hx; rw [Metric.mem_sphere, dist_zero_right] at this; exact this
    have hr_pos : 0 < r := hr.1
    have hr_ne : r ≠ 0 := hr_pos.ne'
    have hrnorm : ‖r • x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hxnorm, mul_one]
    rw [hrnorm]
    have hinvx : r⁻¹ • (r • x) = x := by
      rw [smul_smul, inv_mul_cancel₀ hr_ne, one_smul]
    rw [hinvx]
    have htgt_mem : e.toFun x ∈ e.target := e.map_source' hx
    have hetgnorm : ‖e.toFun x‖ = 1 := by
      have := htgt htgt_mem; rw [Metric.mem_sphere, dist_zero_right] at this; exact this
    have hretnorm : ‖r • e.toFun x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hetgnorm, mul_one]
    rw [hretnorm]
    have hinvet : r⁻¹ • (r • e.toFun x) = e.toFun x := by
      rw [smul_smul, inv_mul_cancel₀ hr_ne, one_smul]
    rw [hinvet]
    have hleft : e.invFun (e.toFun x) = x := e.left_inv' hx
    rw [hleft]

end Problems.Geometry.banach_tarski
