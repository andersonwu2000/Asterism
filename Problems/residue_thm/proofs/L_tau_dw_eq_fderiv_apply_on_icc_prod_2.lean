-- Same shape as the already-proved sibling s10364 (identical statement).
-- Two sub-goals (each matching an already-proved sibling lemma the framework
-- can alias on): (a) inner section-derivWithin identity for `H`, (b) τ-section
-- chain rule for the joint smooth `g`. Combine via `derivWithin_congr` (pointwise
-- rewrite on `Icc`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10402

namespace Problems.residue_thm

def tau_dw_eq_fderiv_apply_on_icc_prod_2 := @Problems.residue_thm.s10402

end Problems.residue_thm
