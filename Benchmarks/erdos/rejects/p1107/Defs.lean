import Mathlib

set_option maxHeartbeats 400000

open Nat Filter

namespace Problems.Erdos.p1107

def SumOfRPowerful (r n : ℕ) : Prop :=
  ∃ s : List ℕ, s.length ≤ r + 1 ∧ (∀ x ∈ s, Nat.Full r x) ∧ s.sum = n

end Problems.Erdos.p1107
