import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_image_triple_backward
import Problems.Minif2f.amc12a_2020_p21.proofs.L_image_triple_forward

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: iff-split on the membership-vs-predicate equivalence.
-- `image_triple_forward` (image → predicate): n = 2^a · 3^b · 5^3 · 7^d for
-- (a,b,d) in the product implies 5 ∣ n (since 5^3 ∣ n) and the lcm/gcd identity.
-- `image_triple_backward` (predicate → image): from 5 ∣ n and the valuations
-- identity, extract the prime exponents and exhibit the (a,b,d) witness.
-- Combinator threads each direction at the universally bound n.
theorem s9634 :
    ∀ n : ℕ, n ∈ ((Finset.Icc 3 8 ×ˢ Finset.Icc 1 4 ×ˢ Finset.Icc 0 1).image
      (fun p : ℕ × ℕ × ℕ => 2^p.1 * 3^p.2.1 * 5^3 * 7^p.2.2)) ↔
        5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n  := by
  intro n
  exact ⟨image_triple_forward n, image_triple_backward n⟩

end Problems.Minif2f.amc12a_2020_p21
