-- Decompose the iterative-flag construction into two pieces:
-- (1) `flag_seq_choose_step` packages the pointwise `∃ vnext` (from `hext`) into a single
--     function `v : Fin d → V` carrying the chain-step equation per index — a Classical.choice
--     repackaging that strips off the existential layer.
-- (2) `flag_seq_span_iic_from_step` runs the induction on `j.val`: with `W 0 = ⊥` as the base
--     and the per-step chain equation, the span of `v '' Set.Iic j` advances by one along `W`.
-- Combining (1) and (2): pick `v` via (1), conclude the span equality via (2), package the ∃.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10848

namespace Problems.LinearAlgebra.schur_triangularization

def flag_seq_build_from_extends := @Problems.LinearAlgebra.schur_triangularization.s10848

end Problems.LinearAlgebra.schur_triangularization
