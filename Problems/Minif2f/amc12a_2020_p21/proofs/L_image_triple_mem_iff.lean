-- Decomposition: iff-split on the membership-vs-predicate equivalence.
-- `image_triple_forward` (image → predicate): n = 2^a · 3^b · 5^3 · 7^d for
-- (a,b,d) in the product implies 5 ∣ n (since 5^3 ∣ n) and the lcm/gcd identity.
-- `image_triple_backward` (predicate → image): from 5 ∣ n and the valuations
-- identity, extract the prime exponents and exhibit the (a,b,d) witness.
-- Combinator threads each direction at the universally bound n.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9634

namespace Problems.Minif2f.amc12a_2020_p21

def image_triple_mem_iff := @Problems.Minif2f.amc12a_2020_p21.s9634

end Problems.Minif2f.amc12a_2020_p21
