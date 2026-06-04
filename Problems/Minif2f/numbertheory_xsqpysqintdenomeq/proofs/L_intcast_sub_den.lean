import Mathlib
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.Defs

namespace Problems.Minif2f.numbertheory_xsqpysqintdenomeq

-- entry_kind: Builder
theorem intcast_sub_den : ∀ (a : ℚ) (n : ℤ), ((↑n : ℚ) - a).den = a.den := by norm_num

end Problems.Minif2f.numbertheory_xsqpysqintdenomeq
