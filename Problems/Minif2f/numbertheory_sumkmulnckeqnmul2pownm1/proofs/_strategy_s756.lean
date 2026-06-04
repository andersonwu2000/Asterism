import Mathlib
import Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1.Defs
import Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1.proofs.L_icc_eq_range_sum_id_choose
import Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1.proofs.L_sum_range_id_mul_choose

namespace Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1

-- Decompose ∑_{k=1}^{n} k * C(n,k) = n * 2^(n-1) into:
--   sum_range_id_mul_choose: same identity over Finset.range (m+1) (abstracts away h₀ via Nat sub).
--   icc_eq_range_sum_id_choose: the k=0 term vanishes, converting Icc 1 n to range (n+1).
-- Combine by rewriting LHS to range form then applying the main identity.
theorem s756 : ∀ (n : ℕ) (h₀ : 0 < n), (∑ k ∈ Finset.Icc 1 n, k * Nat.choose n k) = n * 2 ^ (n - 1)  := by
  intro n _h₀
  have h1 := sum_range_id_mul_choose n
  have h2 := icc_eq_range_sum_id_choose n
  rw [h2, h1]

end Problems.Minif2f.numbertheory_sumkmulnckeqnmul2pownm1
