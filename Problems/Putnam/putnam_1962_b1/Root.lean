import Mathlib
import Problems.Putnam.putnam_1962_b1.Defs

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_1962_b1

theorem main : ∀ (p : ℕ → ℝ → ℝ)
(x y : ℝ)
(n : ℕ)
(h0 : p 0 = fun x : ℝ => 1)
(hp : ∀ n > 0, p n = fun x : ℝ => ∏ i ∈ Finset.range n, (x - i)),
p n (x+y) = ∑ k ∈ Finset.range (n+1), Nat.choose n k * (p k x) * (p (n - k) y) := by sorry

end Problems.Putnam.putnam_1962_b1
