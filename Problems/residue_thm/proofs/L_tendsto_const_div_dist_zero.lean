import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- tendsto_const_div_dist_zero: norm → ∞ at cocompact + reverse triangle + inv → 0
-- closes M / (‖z - z₀‖ - R/2) → 0 by showing the denominator → +∞
theorem tendsto_const_div_dist_zero
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    ∀ M : ℝ, Filter.Tendsto
      (fun z : ℂ => M / (‖z - z₀‖ - R/2))
      (Filter.cocompact ℂ) (nhds 0) := by
  intro M
  -- Step 1: ‖z - z₀‖ → ∞ at cocompact ℂ via reverse triangle inequality
  have h_norm : Filter.Tendsto (fun z : ℂ => ‖z - z₀‖) (Filter.cocompact ℂ) Filter.atTop := by
    rw [Filter.tendsto_atTop]
    intro b
    filter_upwards [(Filter.tendsto_atTop.mp tendsto_norm_cocompact_atTop) (b + ‖z₀‖)] with z hz
    have h_rev := abs_norm_sub_norm_le z z₀
    linarith [le_abs_self (‖z‖ - ‖z₀‖)]
  -- Step 2: ‖z - z₀‖ - R/2 → ∞
  have h_sub : Filter.Tendsto
      (fun z : ℂ => ‖z - z₀‖ - R / 2) (Filter.cocompact ℂ) Filter.atTop := by
    rw [Filter.tendsto_atTop]
    intro b
    filter_upwards [(Filter.tendsto_atTop.mp h_norm (b + R / 2))] with z hz
    linarith
  -- Step 3: M / x → 0 as x → ∞ (via x⁻¹ → 0 and const mult)
  have h_inv : Filter.Tendsto (fun x : ℝ => M / x) Filter.atTop (nhds 0) := by
    have h : Filter.Tendsto (fun x : ℝ => M * x⁻¹) Filter.atTop (nhds (M * 0)) :=
      tendsto_const_nhds.mul tendsto_inv_atTop_zero
    simp only [mul_zero] at h
    exact h.congr (fun x => (div_eq_mul_inv M x).symm)
  exact h_inv.comp h_sub

end Problems.residue_thm
