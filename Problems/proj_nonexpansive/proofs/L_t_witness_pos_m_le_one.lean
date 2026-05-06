-- t_witness_pos_m_le_one: proved by hint: norm_num
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem t_witness_pos_m_le_one (M : ℝ) (hM : 0 < M) (ε : ℝ) (hε : 0 < ε) :
    min 1 (ε / M) ≤ 1 := by norm_num

end Problems.proj_nonexpansive
