import Mathlib
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.Defs

namespace Problems.Minif2f.numbertheory_xsqpysqintdenomeq

-- entry_kind: Builder
theorem rat_sq_den : ∀ q : ℚ, (q ^ 2).den = q.den ^ 2 := by norm_num

end Problems.Minif2f.numbertheory_xsqpysqintdenomeq
