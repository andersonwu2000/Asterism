import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- pointwise_kernel_bound: kernel bound via div_le_div₀ + reverse triangle inequality
-- For w on sphere |w-z₀|=r, reverse triangle gives |w-z| ≥ dist z z₀ - r > 0,
-- so ‖f w / (w-z)‖ = ‖f w‖/‖w-z‖ ≤ M/(dist z z₀ - r) by div_le_div₀.
set_option linter.unusedVariables false in
theorem pointwise_kernel_bound
    {f : ℂ → ℂ} {z₀ : ℂ} {r M : ℝ} (hr : 0 ≤ r)
    (hf : ∀ w ∈ Metric.sphere z₀ r, ‖f w‖ ≤ M)
    {z : ℂ} (hz : r < dist z z₀) :
    ∀ w ∈ Metric.sphere z₀ r, ‖f w / (w - z)‖ ≤ M / (dist z z₀ - r) := by
  intro w hw
  have hwz₀ : dist w z₀ = r := Metric.mem_sphere.mp hw
  have hge : dist z z₀ - r ≤ dist z w := by
    have h3 := dist_triangle z w z₀
    have h4 : dist z₀ w = r := by rw [dist_comm]; exact hwz₀
    linarith
  have hpos : 0 < dist z z₀ - r := by linarith
  have hge2 : dist z z₀ - r ≤ ‖w - z‖ := by
    rw [← dist_eq_norm]
    linarith [dist_comm z w]
  have hwzpos : 0 < ‖w - z‖ := by linarith
  have hM : 0 ≤ M := le_trans (norm_nonneg _) (hf w hw)
  rw [norm_div]
  exact div_le_div₀ hM (hf w hw) hpos hge2
end Problems.residue_thm
