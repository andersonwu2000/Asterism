-- norm_le_of_inner_sq: Uses `real_inner_le_norm` (Cauchy-Schwarz: `⟪w, v⟫_ℝ ≤ ‖w‖ * ‖v‖`) to chain `‖v‖² ≤ ‖w‖ * ‖v‖`, then cancels `‖v‖` via `le_of_mul_le_mul_right` (handling `v = 0` separately with `simp`).
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem norm_le_of_inner_sq : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {v w : X}, ‖v‖ ^ 2 ≤ @inner ℝ _ _ w v → ‖v‖ ≤ ‖w‖ := by
  intro X _ _ v w h
  rcases eq_or_ne v 0 with rfl | hv
  · simp
  · have cs : @inner ℝ _ _ w v ≤ ‖w‖ * ‖v‖ := real_inner_le_norm w v
    have hv_pos : 0 < ‖v‖ := norm_pos_iff.mpr hv
    have key : ‖v‖ ^ 2 ≤ ‖w‖ * ‖v‖ := le_trans h cs
    have hrw : ‖v‖ * ‖v‖ ≤ ‖w‖ * ‖v‖ := by rw [← sq]; exact key
    exact le_of_mul_le_mul_right hrw hv_pos

end Problems.proj_nonexpansive
