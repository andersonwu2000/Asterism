-- t_witness_pos_m_pos: proved by hint: positivity
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem t_witness_pos_m_pos (M : ℝ) (hM : 0 < M) (ε : ℝ) (hε : 0 < ε) :
    0 < min 1 (ε / M) := by positivity

end Problems.proj_nonexpansive
