-- t_witness_pos_m_mul_le: Uses `min_le_right` to bound `min 1 (ε/M) ≤ ε/M`, then `mul_le_mul_of_nonneg_right` to multiply by `M ≥ 0`, and `div_mul_cancel₀` (with `M ≠ 0`) to simplify `(ε/M)*M = ε`.
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem t_witness_pos_m_mul_le (M : ℝ) (hM : 0 < M) (ε : ℝ) (hε : 0 < ε) :
    min 1 (ε / M) * M ≤ ε := by
  calc min 1 (ε / M) * M ≤ ε / M * M :=
        mul_le_mul_of_nonneg_right (min_le_right 1 (ε / M)) hM.le
    _ = ε := div_mul_cancel₀ ε hM.ne'

end Problems.proj_nonexpansive
