import Mathlib

set_option maxHeartbeats 400000

open Filter Asymptotics

namespace Problems.Erdos.p236

def f (n : ℕ) : ℕ :=
  ((List.range (Nat.log2 n + 1)).filter (fun k => Nat.Prime (n - 2^k))).length

end Problems.Erdos.p236
