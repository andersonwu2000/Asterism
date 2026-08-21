import Mathlib

set_option maxHeartbeats 400000

open Filter Real Erdos961

namespace Problems.Erdos.p683

def P (n k : ℕ) : ℕ := (n.choose k).primeFactors.sup id

end Problems.Erdos.p683
