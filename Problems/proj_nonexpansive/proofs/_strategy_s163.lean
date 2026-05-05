import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_s163_sub_1
import Problems.proj_nonexpansive.proofs.L_s163_sub_2

namespace Problems.proj_nonexpansive

theorem s163 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hK : IsClosed K) (hConv : Convex ℝ K) (hNe : K.Nonempty)
    {P : X → X} (hP : IsMetricProjector K P)
    (x z : X) (hz : z ∈ K) :
    @inner ℝ X _ (P x - x) (z - P x) ≥ 0  := by
  have h_le : @inner ℝ X _ (x - P x) (z - P x) ≤ 0 :=
    s163_sub_2 _ _ (by positivity) (s163_sub_1 hK hConv hNe hP x z hz)
  have key : @inner ℝ X _ (P x - x) (z - P x) = -@inner ℝ X _ (x - P x) (z - P x) := by
    simp only [inner_sub_left]
    ring
  linarith

end Problems.proj_nonexpansive
