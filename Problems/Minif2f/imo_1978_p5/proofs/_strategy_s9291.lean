import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_abel_inequality_from_prefix_bound
import Problems.Minif2f.imo_1978_p5.proofs.L_prefix_sum_lower_bound

namespace Problems.Minif2f.imo_1978_p5

-- Classical IMO 1978 P5: split into a prefix-sum bound from injectivity
-- and an Abel-summation inequality that consumes that bound.
-- (1) `prefix_sum_lower_bound`: `a 1..a m` are `m` distinct positive naturals
--     (since `a` is injective and `a 0 = 0`), so
--     `∑_{k=1..m} a k ≥ ∑_{k=1..m} k`.
-- (2) `abel_inequality_from_prefix_bound`: pure Abel summation against weights
--     `c(k) = 1/k²` (`c k - c (k+1) ≥ 0`), folding the prefix bound into the
--     weighted-sum conclusion. Independent of `a` being injective.
-- Combinator is direct application of (2) to (1).
theorem s9291 : ∀ (n : ℕ) (a : ℕ → ℕ) (h₀ : Function.Injective a) (h₁ : a 0 = 0) (h₂ : 0 < n), (∑ k ∈ Finset.Icc 1 n, (1 : ℝ) / k) ≤ ∑ k ∈ Finset.Icc 1 n, (a k : ℝ) / k ^ 2  := by
  intro n a h₀ h₁ h₂
  have h_prefix := prefix_sum_lower_bound n a h₀ h₁
  exact abel_inequality_from_prefix_bound n a h₂ h_prefix

end Problems.Minif2f.imo_1978_p5
