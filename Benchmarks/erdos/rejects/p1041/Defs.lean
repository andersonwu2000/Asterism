import Mathlib

set_option maxHeartbeats 400000

open Polynomial MeasureTheory ENNReal

namespace Problems.Erdos.p1041

noncomputable def length (s : Set ℂ) : ℝ≥0∞ := μH[1] s

end Problems.Erdos.p1041
