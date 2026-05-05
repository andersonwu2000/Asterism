import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s58_sub_1
import Problems.sylvester_gallai.proofs.L_s58_sub_2

namespace Problems.sylvester_gallai

theorem s58 : ∀ (p a b c x z : ℝ × ℝ),
    ¬ Collinear p a b →
    Collinear a b c →
    a ≠ b →
    x ∈ ({a, b, c} : Finset (ℝ × ℝ)) →
    z ∈ ({a, b, c} : Finset (ℝ × ℝ)) →
    x ≠ z →
    ¬ Collinear x p z  := by
  intro p a b c x z hnc hcol hab hx hz hxz
  exact s58_sub_2 p a b c x z hnc hcol hab
    (s58_sub_1 a b c x hx) (s58_sub_1 a b c z hz) hxz

end Problems.sylvester_gallai
