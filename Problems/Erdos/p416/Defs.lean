import Mathlib

set_option maxHeartbeats 400000

open Filter
open scoped Topology Real

namespace Problems.Erdos.p416

noncomputable abbrev V (x : ℝ) : ℝ :=
  open scoped Classical in
  (Finset.Icc 1 ⌊x⌋₊ |>.filter (fun n => ∃ (m : ℕ), m.totient = n)).card

end Problems.Erdos.p416
