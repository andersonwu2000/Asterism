import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_s165_sub_1
import Problems.proj_nonexpansive.proofs.L_s165_sub_2
import Problems.proj_nonexpansive.proofs.L_s165_sub_3

namespace Problems.proj_nonexpansive

theorem s165 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hK : IsClosed K) (hConv : Convex ℝ K) (hNe : K.Nonempty)
    {P : X → X} (hP : IsMetricProjector K P)
    (x y : X) :
    ‖P x - P y‖ ^ 2 ≤ @inner ℝ X _ (x - y) (P x - P y)  := by
  have h1 : @inner ℝ X _ (P x - x) (P y - P x) ≥ 0 :=
    s165_sub_1 hK hConv hNe (P x) x (P y) (hP x).1 (hP x).2 (hP y).1
  have h2 : @inner ℝ X _ (P y - y) (P x - P y) ≥ 0 :=
    s165_sub_1 hK hConv hNe (P y) y (P x) (hP y).1 (hP y).2 (hP x).1
  have h3 : @inner ℝ X _ ((x - y) - (P x - P y)) (P x - P y) ≥ 0 :=
    s165_sub_2 (P x) (P y) x y h1 h2
  exact s165_sub_3 (x - y) (P x - P y) h3

end Problems.proj_nonexpansive
