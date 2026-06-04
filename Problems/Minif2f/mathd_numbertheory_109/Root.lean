-- Direct leaf proof: substitute v k = 2*k-1, then ∑_{k=1}^{n} (2k-1) = n² by induction.
-- For n = 100 the sum is 10000 and 10000 % 7 = 4 (closed by `rw`'s auto-rfl).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_109.Defs
import Problems.Minif2f.mathd_numbertheory_109.proofs._strategy_s519

namespace Problems.Minif2f.mathd_numbertheory_109

def main := @Problems.Minif2f.mathd_numbertheory_109.s519

end Problems.Minif2f.mathd_numbertheory_109
