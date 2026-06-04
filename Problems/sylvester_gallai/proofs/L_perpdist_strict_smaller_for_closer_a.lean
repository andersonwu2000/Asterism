-- Decomposition: reduce the strict ratio inequality to five sub-claims that
-- nlinarith can combine after clearing denominators.
--   (1) h_tdiff: same-side + |t_a-t_f| ≤ |t_b-t_f| forces |t_b-t_a| ≤ |t_b-t_f|.
--   (2) h_newnum: the new numerator factors as (t_b - t_a)^2 * OldNum^2.
--   (3) h_denom: |r-b|^2 * D = OldNum^2 + (t_b-t_f)^2 * D^2 (after subst t_f).
--   (4) h_oldsq_pos: OldNum^2 > 0 from hncol (the determinant is nonzero).
--   (5) h_dsq_pos:  D = |q-p|^2 > 0 from hpq.
-- Combining: |r-b|^2 > 0 from (3,4,5); clear denominators with div_lt_div_iff,
-- rewrite numerator by (2), then nlinarith using (1,3,4,5).
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s10217

namespace Problems.sylvester_gallai

def perpdist_strict_smaller_for_closer_a := @Problems.sylvester_gallai.s10217

end Problems.sylvester_gallai
