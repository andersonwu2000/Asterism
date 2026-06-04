-- Set membership unfolds to `0 < 112 ∧ ∃! k, …`. The positivity conjunct is `decide`;
-- delegate the unique-existence claim to `unique_k_for_112` (the analytical core: bounds
-- give 96 < k < 98, so k = 97 is the unique witness).
import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs._strategy_s759

namespace Problems.Minif2f.aime_1987_p8

def mem_112 := @Problems.Minif2f.aime_1987_p8.s759

end Problems.Minif2f.aime_1987_p8
