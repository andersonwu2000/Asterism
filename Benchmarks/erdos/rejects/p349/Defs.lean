import Mathlib

set_option maxHeartbeats 400000

open Set Filter Real Nat Function

namespace Problems.Erdos.p349

def IsGoodPair (t α : ℝ) : Prop :=
  IsAddComplete (range (fun n ↦ ⌊t * α ^ n⌋))

end Problems.Erdos.p349
