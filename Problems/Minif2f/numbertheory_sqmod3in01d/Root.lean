-- Case split on residue a % 3 ∈ {0,1,2} via omega, then dispatch
-- to a per-residue square computation. Each sub-goal is strictly
-- simpler: it adds a definite `a % 3 = k` hypothesis, reducing the
-- ∀ goal to a single modular arithmetic computation.
import Mathlib
import Problems.Minif2f.numbertheory_sqmod3in01d.Defs
import Problems.Minif2f.numbertheory_sqmod3in01d.proofs._strategy_s754

namespace Problems.Minif2f.numbertheory_sqmod3in01d

def main := @Problems.Minif2f.numbertheory_sqmod3in01d.s754

end Problems.Minif2f.numbertheory_sqmod3in01d
