-- Split the Ioo×Ioo τ-derivative bound into (a) a bound on the closed product
-- Icc×Icc stated with `derivWithin` (continuous on the compact, hence bounded),
-- and (b) the pointwise identification of `deriv` with `derivWithin` on the
-- interior. Combinator: M from (a), rewrite via (b) on Ioo×Ioo ⊆ Icc×Icc.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10343

namespace Problems.residue_thm

def tau_partial_bound_ioo := @Problems.residue_thm.s10343

end Problems.residue_thm
