import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_bound_solutions

namespace Problems.Minif2f.amc12b_2021_p21

-- Abstract away the Finset membership wrapper: the real content
-- is a pointwise bound for any positive real satisfying the
-- equation x^(2^√2) = √2^(2^x). Unpack `x ∈ S` via the spec and
-- apply the pointwise bound.
theorem s9673 : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), ∀ x ∈ S, x ≤ 4  := by
  intro S hS x hx
  have hx' := (hS x).mp hx
  exact bound_solutions x hx'.1 hx'.2


end Problems.Minif2f.amc12b_2021_p21
