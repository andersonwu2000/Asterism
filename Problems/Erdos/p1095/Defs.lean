import Mathlib

set_option maxHeartbeats 400000

open Nat hiding log
open Real Filter
open scoped Asymptotics Topology

namespace Problems.Erdos.p1095

noncomputable def g (k : ℕ) : ℕ := sInf {m | k + 1 < m ∧ k < (m.choose k).minFac}

-- TODO: Add erdos_1095.

end Problems.Erdos.p1095
