-- Decompose `S.card ≤ 2` via two structural facts about the equation
-- `x ^ (2 ^ √2) = √2 ^ (2 ^ x)` on (0, ∞):
--   (a) every positive solution is either √2 or strictly greater than 3;
--   (b) at most one positive solution lies above 3.
-- Then S ⊆ insert √2 (S.filter (3 < ·)), and the filtered part has card ≤ 1.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9668

namespace Problems.Minif2f.amc12b_2021_p21

def card_le_two := @Problems.Minif2f.amc12b_2021_p21.s9668

end Problems.Minif2f.amc12b_2021_p21
