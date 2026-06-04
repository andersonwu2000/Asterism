import Mathlib
import Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1.Defs

namespace Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1

-- icc_eq_range_sum_id_choose: Finset.sum_subset drops the k=0 term (0 * C(n,0) = 0),
-- equating the Icc 1 n sum to the range (n+1) sum.
theorem icc_eq_range_sum_id_choose : ∀ (n : ℕ),
    ∑ k ∈ Finset.Icc 1 n, k * Nat.choose n k =
    ∑ k ∈ Finset.range (n + 1), k * Nat.choose n k := by
  intro n
  apply Finset.sum_subset
  · intro x; simp [Finset.mem_Icc, Finset.mem_range]
  · intro x hx hx'
    simp [Finset.mem_range] at hx
    simp [Finset.mem_Icc] at hx'
    have : x = 0 := by omega
    simp [this]

end Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1
