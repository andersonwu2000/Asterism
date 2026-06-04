import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs.L_bounded_involution_fixed

namespace Problems.Minif2f.imo_1987_p4

-- Abstract the goal to the combinatorial fact: any self-inverse map on {0,…,1986}
-- (g(g a) = a whenever a < 1987) has a fixed point — independent of f, hff. The
-- closer applies the sub-goal at g = fun a => f a % 1987, with hg from Nat.mod_lt
-- and hgg = hinv verbatim.
theorem s9723 (f : ℕ → ℕ) (hff : ∀ n, f (f n) = n + 1987)
    (hinv : ∀ a, a < 1987 → f (f a % 1987) % 1987 = a) :
    ∃ a, a < 1987 ∧ f a % 1987 = a  := by
  have h_bounded_involution_fixed := bounded_involution_fixed
  exact h_bounded_involution_fixed (fun a => f a % 1987)
    (fun a _ => Nat.mod_lt _ (by norm_num)) hinv

end Problems.Minif2f.imo_1987_p4
