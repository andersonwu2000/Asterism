import Mathlib

set_option maxHeartbeats 400000

open EuclideanGeometry Filter Asymptotics

namespace Problems.Erdos.p101

noncomputable def numLinesWithFourPointMax (n : ℕ) : ℕ :=
  sSup {((linesWithPointsFor 4 S).ncard)| (S : Set ℝ²)
    (_ : S.ncard = n) (_ : S.Finite) (_ : NonCollinearFor 5 S)}

end Problems.Erdos.p101
