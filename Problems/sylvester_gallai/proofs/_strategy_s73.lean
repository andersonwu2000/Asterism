import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s73_sub_1
import Problems.sylvester_gallai.proofs.L_s73_sub_2
import Problems.sylvester_gallai.proofs.L_s73_sub_3

namespace Problems.sylvester_gallai

theorem s73 : ∀ (p a b c z : ℝ × ℝ),
    Collinear a b c →
    a ≠ b →
    z ∈ ({a, b, c} : Finset (ℝ × ℝ)) →
    ((c.1 - z.1) * (p.2 - z.2) - (c.2 - z.2) * (p.1 - z.1)) ^ 2 *
    ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2) =
    ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
    ((c.1 - z.1) ^ 2 + (c.2 - z.2) ^ 2)  := by
  intro p a b c z hcol hab hz
  simp only [Finset.mem_insert, Finset.mem_singleton] at hz
  rcases hz with ha | hb | hc
  · rw [ha]; exact s73_sub_1 p a b c hcol hab
  · rw [hb]; exact s73_sub_2 p a b c hcol hab
  · rw [hc]; exact s73_sub_3 p a b c hcol hab

end Problems.sylvester_gallai
