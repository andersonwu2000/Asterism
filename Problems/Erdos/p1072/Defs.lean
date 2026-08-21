import Mathlib

set_option maxHeartbeats 400000

open Nat Filter Finset Set
open scoped Topology

namespace Problems.Erdos.p1072

noncomputable def f (p : ℕ) : ℕ := sInf {n | (n)! + 1 ≡ 0 [MOD p]}

end Problems.Erdos.p1072
