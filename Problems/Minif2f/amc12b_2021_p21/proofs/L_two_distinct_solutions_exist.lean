-- Decomposition: pick a := √2 (always in S by reflexivity) and b := c where c ≥ 2
-- is another root of the equation. Sub-goal 1 establishes √2 ∈ S; sub-goal 2 produces
-- c ∈ S with 2 ≤ c. Distinctness follows since √2 < 2 ≤ c, and a + b = √2 + c ≥ 2
-- since √2 ≥ 0 and c ≥ 2.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9473

namespace Problems.Minif2f.amc12b_2021_p21

def two_distinct_solutions_exist := @Problems.Minif2f.amc12b_2021_p21.s9473

end Problems.Minif2f.amc12b_2021_p21
