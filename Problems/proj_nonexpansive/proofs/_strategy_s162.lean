import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_s162_sub_1
import Problems.proj_nonexpansive.proofs.L_s162_sub_2
import Problems.proj_nonexpansive.proofs.L_s162_sub_3
import Problems.proj_nonexpansive.proofs.L_s162_sub_4

namespace Problems.proj_nonexpansive

theorem s162 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖  := by
  intro X _ _ K hK hConv hNe P hP x y
  have h2 : ‖P x - P y‖ ^ 2 ≤ @inner ℝ X _ (x - y) (P x - P y) :=
    s162_sub_2 hK hConv hNe hP x y
  have h3 : @inner ℝ X _ (x - y) (P x - P y) ≤ ‖x - y‖ * ‖P x - P y‖ :=
    s162_sub_3 (x - y) (P x - P y)
  exact s162_sub_4 (P x - P y) (x - y) (h2.trans h3)

end Problems.proj_nonexpansive
