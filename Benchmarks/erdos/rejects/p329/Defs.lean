import Mathlib

set_option maxHeartbeats 400000

open Function Set Filter

namespace Problems.Erdos.p329

noncomputable def sqrtPartialDensity (A : Set ℕ) (N : ℕ) : ℝ :=
  (A ∩ Set.Icc 1 N).ncard / (N : ℝ).sqrt

noncomputable def sidonUpperDensity (A : Set ℕ) : ℝ :=
  limsup (fun N => sqrtPartialDensity A N) atTop

end Problems.Erdos.p329
