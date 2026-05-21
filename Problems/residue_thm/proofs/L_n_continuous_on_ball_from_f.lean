import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- n_continuous_on_ball_from_f: integer label is ContinuousOn the ball via
-- discrete-topology lifting: cast (n w : ℂ) = f w / (2πi) is continuous,
-- and Int.cast is an embedding (integers are isolated in ℂ, separation ≥ 1),
-- so a continuous ℂ-valued function agreeing with Int.cast ∘ n forces n
-- to be locally constant, hence continuous in the discrete topology on ℤ.
-- entry_kind: Builder
theorem n_continuous_on_ball_from_f
    {z : ℂ} {r : ℝ}
    (hr : 0 < r)
    {f : ℂ → ℂ}
    (hf : ContinuousOn f (Metric.ball z r))
    {n : ℂ → ℤ}
    (hfn : ∀ w ∈ Metric.ball z r,
              f w = 2 * Real.pi * Complex.I * (n w : ℂ)) :
    ContinuousOn n (Metric.ball z r) := by
  have h2pi : (2 * ↑Real.pi * Complex.I : ℂ) ≠ 0 :=
    mul_ne_zero (mul_ne_zero (by norm_num) (by exact_mod_cast Real.pi_ne_zero)) Complex.I_ne_zero
  have hcast : ContinuousOn (fun w => (n w : ℂ)) (Metric.ball z r) := by
    apply (hf.div_const (2 * Real.pi * Complex.I)).congr
    intro w hw
    change (n w : ℂ) = f w / (2 * ↑Real.pi * Complex.I)
    rw [hfn w hw]
    field_simp [h2pi]
  intro w₀ hw₀
  have hndis : nhds (n w₀) = pure (n w₀) := congr_fun (nhds_discrete ℤ) (n w₀)
  change Filter.Tendsto n (nhdsWithin w₀ (Metric.ball z r)) (nhds (n w₀))
  rw [hndis, Filter.tendsto_pure]
  have hclose : ∀ᶠ w in nhdsWithin w₀ (Metric.ball z r), ‖(n w : ℂ) - (n w₀ : ℂ)‖ < 1 := by
    have hconst : ContinuousWithinAt (fun _ : ℂ => (n w₀ : ℂ)) (Metric.ball z r) w₀ :=
      continuousWithinAt_const
    have h1 : ContinuousWithinAt (fun w => ‖(n w : ℂ) - (n w₀ : ℂ)‖) (Metric.ball z r) w₀ :=
      ((hcast w₀ hw₀).sub hconst).norm
    exact h1.tendsto.eventually (Iio_mem_nhds (by simp))
  filter_upwards [hclose] with w hw
  have hlt : ‖((n w - n w₀ : ℤ) : ℂ)‖ < 1 := by push_cast; exact hw
  rw [Complex.norm_intCast, ← Int.cast_abs] at hlt
  have habs : |n w - n w₀| < (1 : ℤ) := by exact_mod_cast hlt
  rw [abs_lt] at habs
  omega

end Problems.residue_thm
