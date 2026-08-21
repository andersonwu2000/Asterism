import Mathlib

set_option maxHeartbeats 400000

open Nat Finset Set Filter

namespace Problems.Erdos.p291

def L (n : ℕ) : ℕ :=
  (Finset.Icc 1 n).lcm (fun x ↦ x)

def a (n : ℕ) : ℕ :=
  ∑ k ∈ Finset.Icc 1 n, L n / k

end Problems.Erdos.p291
