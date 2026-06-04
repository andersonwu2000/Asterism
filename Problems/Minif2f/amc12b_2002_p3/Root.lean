-- Split S.card = 1 into two leaf claims: (3 : ℕ) ∈ S, and S ⊆ {3}.
-- Antisymm gives S = {3}; Finset.card_singleton closes. Each sub-goal is strictly
-- simpler: three_in_s reduces to checking 3^2+2-3*3=2 is prime; subset_singleton_three
-- bounds membership by ruling out n=0,1,2 and showing (n-1)(n-2) is composite for n≥4.
import Mathlib
import Problems.Minif2f.amc12b_2002_p3.Defs
import Problems.Minif2f.amc12b_2002_p3.proofs._strategy_s9379

namespace Problems.Minif2f.amc12b_2002_p3

def main := @Problems.Minif2f.amc12b_2002_p3.s9379

end Problems.Minif2f.amc12b_2002_p3
