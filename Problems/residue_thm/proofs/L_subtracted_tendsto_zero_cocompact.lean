import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- subtracted_tendsto_zero_cocompact: split P z → 0 and residue/(z-a) → 0 via cobounded inv
theorem subtracted_tendsto_zero_cocompact
    {P : ℂ → ℂ} {a : ℂ}
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0)) :
    Filter.Tendsto (fun z => P z - Complex.residue P a / (z - a))
      (Filter.cocompact ℂ) (nhds 0) := by
  have h_inv : Filter.Tendsto (fun z : ℂ => (z - a)⁻¹) (Filter.cocompact ℂ) (nhds 0) := by
    rw [← Metric.cobounded_eq_cocompact]
    exact Filter.tendsto_inv₀_cobounded.comp (tendsto_sub_const_cobounded a)
  have h2 : Filter.Tendsto (fun z : ℂ => Complex.residue P a / (z - a))
      (Filter.cocompact ℂ) (nhds 0) := by
    have h_mul := (tendsto_const_nhds (x := Complex.residue P a)
        (f := Filter.cocompact ℂ)).mul h_inv
    simp only [mul_zero] at h_mul
    simp only [div_eq_mul_inv]
    exact h_mul
  have h_final := hP_tendsto.sub h2
  simpa using h_final

end Problems.residue_thm
