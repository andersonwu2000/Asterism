-- Decomposition: derive m ≠ 0 inline from m ∣ 5*10! ≠ 0, then invoke an abstract
-- factorization-product identity over the fixed prime support {2,3,5,7}.
-- Sub-goal `prime_pow_product_formula_2357` drops the lcm/gcd/divisibility
-- premises and only needs k ≠ 0 + support ⊆ {2,3,5,7} — strictly simpler.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9817

namespace Problems.Minif2f.amc12a_2020_p21

def canonical_form_from_support_2357 := @Problems.Minif2f.amc12a_2020_p21.s9817

end Problems.Minif2f.amc12a_2020_p21
