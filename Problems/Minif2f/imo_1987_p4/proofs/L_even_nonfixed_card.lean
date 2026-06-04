-- Decompose `2 ∣ #{a < 1987 | g a ≠ a}` via trichotomy + the involution-induced bijection.
-- (1) `nonfixed_split_lt_gt`: split the non-fixed-point count into `a < g a` plus `g a < a`.
-- (2) `lt_card_eq_gt_card`: the involution `g` bijects `{a < g a}` with `{g a < a}`.
-- Adding two equal cardinalities yields `2 * _`, hence `2 ∣ _`.
import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs._strategy_s9784

namespace Problems.Minif2f.imo_1987_p4

def even_nonfixed_card := @Problems.Minif2f.imo_1987_p4.s9784

end Problems.Minif2f.imo_1987_p4
