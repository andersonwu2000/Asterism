import Mathlib

set_option maxHeartbeats 400000

open Filter EuclideanGeometry

namespace Problems.Erdos.p94

noncomputable def regularNGon (n : ℕ) : Finset ℝ² :=
  (Finset.range n).image fun k : ℕ =>
    !₂[Real.cos (2 * Real.pi * k / n), Real.sin (2 * Real.pi * k / n)]

end Problems.Erdos.p94
