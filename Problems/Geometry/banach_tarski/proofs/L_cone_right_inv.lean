import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- cone_right_inv: radial-lift right-inverse via sphere norm = 1 and PartialEquiv.right_inv'
-- cone_right_inv: radial-lift right-inverse via sphere norm = 1 and PartialEquiv.right_inv'
-- For y = r•x with x ∈ e.target (unit sphere), normalize by ‖y‖=r, apply invFun then toFun.

theorem cone_right_inv (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} →
      (fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z))
        ((fun z => ‖z‖ • e.invFun (‖z‖⁻¹ • z)) y) = y := by
    intro y hy
    obtain ⟨r, hr, x, hx, rfl⟩ := hy
    simp only []
    have hxnorm : ‖x‖ = 1 := by
      have := htgt hx; rw [Metric.mem_sphere, dist_zero_right] at this; exact this
    have hr_pos : 0 < r := hr.1
    have hr_ne : r ≠ 0 := hr_pos.ne'
    have hrnorm : ‖r • x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hxnorm, mul_one]
    rw [hrnorm]
    have hinvx : r⁻¹ • (r • x) = x := by
      rw [smul_smul, inv_mul_cancel₀ hr_ne, one_smul]
    rw [hinvx]
    have hsrc_mem : e.invFun x ∈ e.source := e.map_target' hx
    have hinvnorm : ‖e.invFun x‖ = 1 := by
      have := hsrc hsrc_mem; rw [Metric.mem_sphere, dist_zero_right] at this; exact this
    have hreinvnorm : ‖r • e.invFun x‖ = r := by
      rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hinvnorm, mul_one]
    rw [hreinvnorm]
    have hinvinv : r⁻¹ • (r • e.invFun x) = e.invFun x := by
      rw [smul_smul, inv_mul_cancel₀ hr_ne, one_smul]
    rw [hinvinv]
    have hright : e.toFun (e.invFun x) = x := e.right_inv' hx
    rw [hright]

end Problems.Geometry.banach_tarski

