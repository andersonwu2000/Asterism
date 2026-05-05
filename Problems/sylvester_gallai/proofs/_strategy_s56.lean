import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s56_sub_1
import Problems.sylvester_gallai.proofs.L_s56_sub_2
import Problems.sylvester_gallai.proofs.L_s56_sub_3

namespace Problems.sylvester_gallai

theorem s56 : ∀ (p a b c x z : ℝ × ℝ),
    Collinear a b c →
    a ≠ b →
    x ∈ ({a, b, c} : Finset (ℝ × ℝ)) →
    z ∈ ({a, b, c} : Finset (ℝ × ℝ)) →
    ((x.1 - z.1) * (p.2 - z.2) - (x.2 - z.2) * (p.1 - z.1)) ^ 2 *
    ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2) =
    ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
    ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2)  := by
  intro p a b c x z hcol hab hx hz
  -- rw [h] rewrites x→val in the goal only; avoids subst eliminating context variables
  rcases Finset.mem_insert.mp hx with (h | hx)
  · rw [h]; exact s56_sub_1 p a b c z hcol hab hz
  · rcases Finset.mem_insert.mp hx with (h | hx)
    · rw [h]; exact s56_sub_2 p a b c z hcol hab hz
    · rw [Finset.mem_singleton] at hx
      rw [hx]; exact s56_sub_3 p a b c z hcol hab hz

end Problems.sylvester_gallai
