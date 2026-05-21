-- For w on the ε-sphere: γ avoids w (triangle inequality from hε_sep),
-- so reduce to a pointwise lemma (∀ z avoided by γ, the integral equals
-- -(2πi)·windingNumber γ z) — one sign flip away from winding_integral_formula.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10568

namespace Problems.residue_thm

def path_int_eq_neg_winding_at_w := @Problems.residue_thm.s10568

end Problems.residue_thm
