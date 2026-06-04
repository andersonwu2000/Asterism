-- Recast `Fin n ≅ Fin (∑ l)` via `subst hsum`, then take `e := finSigmaFinEquiv.symm`
-- (position ↦ block × within-block offset) with `o t := ∑_{j<t} l j` (prefix sums of
-- block lengths). Split into two strictly simpler claims:
--   `fin_sigma_offset_decomp` — pure `finSigmaFinEquiv_apply` rewrite (no S, no hstart).
--   `start_offset_zero_fin_sigma` — start-iff-offset-zero at the concrete equiv (re-uses the
--     prefix-sum uniqueness lemma proved at sibling level).
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11059

namespace Problems.LinearAlgebra.jordan_normal_form

def block_equiv_from_gaps := @Problems.LinearAlgebra.jordan_normal_form.s11059

end Problems.LinearAlgebra.jordan_normal_form
