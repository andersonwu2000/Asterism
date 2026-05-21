import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- g_bounded_on_sphere: continuous function on compact sphere has a uniform norm bound
-- Uses isCompact_sphere + NormedSpace.sphere_nonempty + IsCompact.exists_isMaxOn
-- entry_kind: Builder
theorem g_bounded_on_sphere
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r)) :
    ∃ Mg : ℝ, 0 ≤ Mg ∧ ∀ w ∈ Metric.sphere c r, ‖g w‖ ≤ Mg := by
  have hcomp : IsCompact (Metric.sphere c r) := isCompact_sphere c r
  have hne : (Metric.sphere c r).Nonempty := NormedSpace.sphere_nonempty.mpr hr.le
  obtain ⟨x, hx, hxmax⟩ := hcomp.exists_isMaxOn hne hg.norm
  exact ⟨‖g x‖, norm_nonneg _, fun w hw => hxmax hw⟩

end Problems.residue_thm
