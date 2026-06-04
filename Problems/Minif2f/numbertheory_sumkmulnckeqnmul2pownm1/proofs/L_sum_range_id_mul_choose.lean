import Mathlib
import Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1.Defs

namespace Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1

-- entry_kind: Builder
theorem sum_range_id_mul_choose : ∀ (m : ℕ), ∑ k ∈ Finset.range (m + 1), k * Nat.choose m k = m * 2 ^ (m - 1) := by exact fun m ↦ Nat.sum_range_mul_choose m

end Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1
