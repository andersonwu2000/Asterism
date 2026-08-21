import Mathlib

set_option maxHeartbeats 400000

open Asymptotics Filter

namespace Problems.Erdos.p859

def DivisorSumSet (t : ℕ) := { n : ℕ | ∃ s ⊆ Nat.divisors n, t = ∑ i ∈ s, i }

end Problems.Erdos.p859
