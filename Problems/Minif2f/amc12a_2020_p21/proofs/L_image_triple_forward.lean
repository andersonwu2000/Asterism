-- Decomposition: conjunction-split on the predicate side.
-- `forward_dvd_five` (image → 5 ∣ n): n = 2^a · 3^b · 5^3 · 7^d in image
--   has 5^3 ∣ n, hence 5 ∣ n. Leaf-level divisibility, marked Builder.
-- `forward_lcm_gcd_eq` (image → lcm/gcd identity): from the same factorization
--   with bounds a ∈ [3,8], b ∈ [1,4], d ∈ [0,1], compute
--   lcm(5!, n) = n and gcd(10!, n) = n/5, giving lcm = 5·gcd. Marked Backward.
-- Combinator threads both at the universally bound n via And.intro.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9679

namespace Problems.Minif2f.amc12a_2020_p21

def image_triple_forward := @Problems.Minif2f.amc12a_2020_p21.s9679

end Problems.Minif2f.amc12a_2020_p21
