import Mathlib

set_option maxHeartbeats 400000

open Finset Nat

namespace Problems.Erdos.p1093

noncomputable def deficiency (n k : ℕ) : ℕ :=
  #{i ∈ range k | n - i ∈ smoothNumbers k}

end Problems.Erdos.p1093
