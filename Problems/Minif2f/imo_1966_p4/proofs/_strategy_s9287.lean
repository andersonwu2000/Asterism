import Mathlib
import Problems.Minif2f.imo_1966_p4.Defs
import Problems.Minif2f.imo_1966_p4.proofs.L_pow_cot_sum_telescopes
import Problems.Minif2f.imo_1966_p4.proofs.L_pow_csc_eq_cot_diff

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1966_p4

-- Decomposition: split into (1) pointwise identity 1/sin(2^k·x) = cot(2^(k-1)·x) − cot(2^k·x),
-- and (2) the pure algebra telescoping sum. The combinator is `Finset.sum_congr` over Icc 1 n
-- to rewrite each summand via (1), then close with (2).
theorem s9287 : ∀ (n : ℕ) (x : ℝ) (h₀ : ∀ k : ℕ, 0 < k → ∀ m : ℤ, x ≠ m * π / 2 ^ k) (h₁ : 0 < n), (∑ k ∈ Finset.Icc 1 n, 1 / Real.sin (2 ^ k * x)) = 1 / Real.tan x - 1 / Real.tan (2 ^ n * x)  := by
  intro n x h₀ h₁
  have h_pointwise := pow_csc_eq_cot_diff n x h₀ h₁
  have h_telescope := pow_cot_sum_telescopes n x h₀ h₁
  calc (∑ k ∈ Finset.Icc 1 n, 1 / Real.sin (2 ^ k * x))
      = ∑ k ∈ Finset.Icc 1 n, (1 / Real.tan (2 ^ (k-1) * x) - 1 / Real.tan (2 ^ k * x)) := by
        refine Finset.sum_congr rfl (fun k hk => ?_)
        exact h_pointwise k (Finset.mem_Icc.mp hk).1
    _ = 1 / Real.tan x - 1 / Real.tan (2 ^ n * x) := h_telescope

end Problems.Minif2f.imo_1966_p4
