-- Direct proof: hypotheses h₁ ∧ h₂ are inconsistent (independent of a's sign).
-- f x = Real.sqrt _ ≥ 0 always, so {x | 0 ≤ f x} = univ; h₂ then forces
-- -1 ∈ f '' univ, contradicting Real.sqrt_nonneg. From False, a = -4 follows.
import Mathlib
import Problems.Minif2f.amc12a_2003_p25.Defs
import Problems.Minif2f.amc12a_2003_p25.proofs._strategy_s9257

namespace Problems.Minif2f.amc12a_2003_p25

def a_neg_eq_neg_four := @Problems.Minif2f.amc12a_2003_p25.s9257

end Problems.Minif2f.amc12a_2003_p25
