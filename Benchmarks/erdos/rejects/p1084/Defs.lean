import Mathlib

set_option maxHeartbeats 400000

open Finset Filter Metric Real
open scoped EuclideanGeometry

namespace Problems.Erdos.p1084

noncomputable def f (d n : ℕ) : ℕ :=
  ⨆ (s : Finset (ℝ^ d)) (_ : s.card = n) (_ : IsSeparated' 1 (s : Set (ℝ^ d))), unitDistNum s

-- TODO: Add erdos_1084.

end Problems.Erdos.p1084
