-- t_witness_zero_m: Witness `t = 1` closes this goal directly: `one_pos` and `le_refl 1` handle the first two conjuncts, and `linarith` reduces `1 * 0 ≤ ε` to `0 ≤ ε` which follows immediately from `hε : 0 < ε`.
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem t_witness_zero_m (ε : ℝ) (hε : 0 < ε) : ∃ t : ℝ, 0 < t ∧ t ≤ 1 ∧ t * 0 ≤ ε := by
  exact ⟨1, one_pos, le_refl 1, by linarith⟩

end Problems.proj_nonexpansive
