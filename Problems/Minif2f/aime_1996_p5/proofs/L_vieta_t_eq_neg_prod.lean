-- Direct nlinarith closure: Vieta on g for distinct roots a+b, b+c, c+a.
-- Rewriting h₅,h₆,h₇ via h₁ turns the three g-evaluations into the cubic
-- equations whose Vieta combination yields t = -((a+b)(b+c)(c+a)). Distinctness
-- of a+b, b+c, c+a is derived from h₈ (pairwise a≠b, b≠c, a≠c) and serves as
-- nlinarith hint guards (sq_nonneg of pairwise differences encode them).
import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs
import Problems.Minif2f.aime_1996_p5.proofs._strategy_s9397

namespace Problems.Minif2f.aime_1996_p5

def vieta_t_eq_neg_prod := @Problems.Minif2f.aime_1996_p5.s9397

end Problems.Minif2f.aime_1996_p5
