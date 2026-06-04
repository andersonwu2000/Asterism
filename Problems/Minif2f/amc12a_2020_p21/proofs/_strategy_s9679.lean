import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_forward_dvd_five
import Problems.Minif2f.amc12a_2020_p21.proofs.L_forward_lcm_gcd_eq

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: conjunction-split on the predicate side.
-- `forward_dvd_five` (image → 5 ∣ n): n = 2^a · 3^b · 5^3 · 7^d in image
--   has 5^3 ∣ n, hence 5 ∣ n. Leaf-level divisibility, marked Builder.
-- `forward_lcm_gcd_eq` (image → lcm/gcd identity): from the same factorization
--   with bounds a ∈ [3,8], b ∈ [1,4], d ∈ [0,1], compute
--   lcm(5!, n) = n and gcd(10!, n) = n/5, giving lcm = 5·gcd. Marked Backward.
-- Combinator threads both at the universally bound n via And.intro.
theorem s9679 : ∀ n : ℕ, n ∈ ((Finset.Icc 3 8 ×ˢ Finset.Icc 1 4 ×ˢ Finset.Icc 0 1).image
      (fun p : ℕ × ℕ × ℕ => 2^p.1 * 3^p.2.1 * 5^3 * 7^p.2.2)) →
        5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n  := by
  intro n hmem
  have h_dvd := forward_dvd_five n hmem
  have h_lcm_gcd := forward_lcm_gcd_eq n hmem
  exact ⟨h_dvd, h_lcm_gcd⟩

end Problems.Minif2f.amc12a_2020_p21
