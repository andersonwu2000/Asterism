-- Schur trick: build witness k := r - 1 - i. Two bounds (i < r ≤ 2i) come from
-- size analysis (degenerate case ruled out by ⌊√(p/3)⌋ < i); divisibility comes
-- from algebraic identity (r-1-i ≡ -1-i mod r ⇒ (r-1-i)²+(r-1-i)+p ≡ i²+i+p).
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9790

namespace Problems.Minif2f.imo_1987_p6

def exists_small_witness := @Problems.Minif2f.imo_1987_p6.s9790

end Problems.Minif2f.imo_1987_p6
