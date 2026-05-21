import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_param_int_deriv_eq_dw_swap
import Problems.residue_thm.proofs.L_param_int_dw_continuous_on_ball

namespace Problems.residue_thm

-- Decompose parametric integral continuity by swapping `deriv γ` for
-- `derivWithin γ (Icc 0 1)` a.e. on [0,1] (junk at endpoints, see LESSONS),
-- proving continuity of the cleaner derivWithin-integral, then transporting
-- back via `ContinuousOn.congr`.
theorem s10593
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, r < dist (γ t) z) :
    ContinuousOn (fun w => ∫ t in (0:ℝ)..1, deriv γ t / (γ t - w))
      (Metric.ball z r)  := by
  have h_eq := param_int_deriv_eq_dw_swap hγ hr h_avoid
  have h_cont := param_int_dw_continuous_on_ball hγ hr h_avoid
  exact h_cont.congr (fun w hw => h_eq w hw)

end Problems.residue_thm
