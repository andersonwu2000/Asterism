import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s50_sub_1
import Problems.sylvester_gallai.proofs.L_s50_sub_2
import Problems.sylvester_gallai.proofs.L_s50_sub_3

namespace Problems.sylvester_gallai

theorem s50 : ∀ (p a b c : ℝ × ℝ),
    ¬ Collinear p a b → Collinear a b c →
    a ≠ b → c ≠ a → c ≠ b →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧ ¬ Collinear x p z ∧
      ((x.1 - z.1) * (p.2 - z.2) - (x.2 - z.2) * (p.1 - z.1)) ^ 2 *
      ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2) <
      ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c hnc hcol hab hca hcb
  obtain ⟨x, hx, z, hz, hxz, hsize⟩ := s50_sub_2 p a b c hnc hcol hab hca hcb
  have hncxpz : ¬ Collinear x p z := s50_sub_3 p a b c x z hnc hcol hab hx hz hxz
  have hid : ((x.1 - z.1) * (p.2 - z.2) - (x.2 - z.2) * (p.1 - z.1)) ^ 2 *
             ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2) =
             ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
             ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) :=
    s50_sub_1 p a b c x z hcol hab hx hz
  have hd_ne : (p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1) ≠ 0 := by
    intro heq
    apply hnc
    unfold Collinear
    linarith
  have hmul : ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
              ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
              ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
              ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2) :=
    mul_lt_mul_of_pos_left hsize (sq_pos_of_ne_zero hd_ne)
  exact ⟨x, hx, z, hz, hxz, hncxpz, by linarith⟩

end Problems.sylvester_gallai
