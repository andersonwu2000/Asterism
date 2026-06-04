import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs

namespace Problems.Minif2f.aime_1987_p8

-- entry_kind: Builder
theorem bounds_for_97 : (8 : ℝ) / 15 < (112 : ℝ) / (112 + (97 : ℕ))
    ∧ (112 : ℝ) / (112 + (97 : ℕ)) < 7 / 13 := by norm_num

end Problems.Minif2f.aime_1987_p8
