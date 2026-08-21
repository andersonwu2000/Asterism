import Mathlib

set_option maxHeartbeats 400000

open Nat Filter Finset
open scoped Asymptotics Topology Nat

namespace Problems.Erdos.p394

noncomputable def t (k n : ℕ) : ℕ :=
  sInf { m : ℕ | 0 < m ∧ n ∣ ∏ i ∈ range k, (m + i) }

end Problems.Erdos.p394
