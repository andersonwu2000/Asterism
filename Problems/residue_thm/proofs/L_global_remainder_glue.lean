-- Decompose `global_remainder_glue` into (1) analytic-glue existence of `g`
-- with the pointwise identity on `U \ T`, and (2) residue equality at each pole.
-- Combinator: obtain `(g, hg_anal, hg_pw)` from (1); package `(g, hg_anal, hg_pw, h_res)`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10456

namespace Problems.residue_thm

def global_remainder_glue := @Problems.residue_thm.s10456

end Problems.residue_thm
