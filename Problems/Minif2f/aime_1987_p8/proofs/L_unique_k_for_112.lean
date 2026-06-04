-- Split `∃! k, P k` (P = ratio bounds for 112/(112+k)) into witness (k=97) + uniqueness.
-- `bounds_for_97`: pure numeric check that k=97 satisfies both bounds (Builder).
-- `k_eq_97_from_bounds`: any y satisfying both bounds must equal 97 (Backward;
-- clear denominators, get 96 < y < 98 over ℕ, then omega). Combined via the
-- `⟨witness, prop_at_witness, uniqueness⟩` constructor for `ExistsUnique`.
import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs._strategy_s9394

namespace Problems.Minif2f.aime_1987_p8

def unique_k_for_112 := @Problems.Minif2f.aime_1987_p8.s9394

end Problems.Minif2f.aime_1987_p8
