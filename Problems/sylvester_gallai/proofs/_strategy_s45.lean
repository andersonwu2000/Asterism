import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s45_sub_1
import Problems.sylvester_gallai.proofs.L_s45_sub_2
import Problems.sylvester_gallai.proofs.L_s45_sub_3
import Problems.sylvester_gallai.proofs.L_s45_sub_4
import Problems.sylvester_gallai.proofs.L_s45_sub_5

namespace Problems.sylvester_gallai

open Classical in
theorem s45 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ a ∈ P, ∃ b ∈ P,
      a ≠ b ∧ ¬ Collinear p a b ∧
      ∀ q ∈ P, ∀ x ∈ P, ∀ y ∈ P,
        x ≠ y → ¬ Collinear q x y →
        ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
        ((x.1 - y.1) ^ 2 + (x.2 - y.2) ^ 2) ≤
        ((q.1 - y.1) * (x.2 - y.2) - (q.2 - y.2) * (x.1 - y.1)) ^ 2 *
        ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2)  := by
  intro P hP
  have hTne := s45_sub_1 P hP
  let g : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) → ℝ := fun t =>
    ((t.1.1 - t.2.2.1) * (t.2.1.2 - t.2.2.2) - (t.1.2 - t.2.2.2) * (t.2.1.1 - t.2.2.1)) ^ 2 /
    ((t.2.1.1 - t.2.2.1) ^ 2 + (t.2.1.2 - t.2.2.2) ^ 2)
  obtain ⟨⟨p, a, b⟩, hmem, hmin⟩ := Finset.exists_min_image _ g hTne
  simp only [Finset.mem_filter, Finset.mem_product] at hmem
  obtain ⟨⟨hp, ha, hb⟩, hab, hnc⟩ := hmem
  refine ⟨p, hp, a, ha, b, hb, hab, hnc, ?_⟩
  intro q hq x hx y hy hxy hnc'
  have hd_ab : 0 < (a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2 := s45_sub_3 a b hab
  have hd_xy : 0 < (x.1 - y.1) ^ 2 + (x.2 - y.2) ^ 2 := s45_sub_3 x y hxy
  have hmem' := s45_sub_4 P q x y hq hx hy hxy hnc'
  have hle : g (p, a, b) ≤ g (q, x, y) := hmin _ hmem'
  exact s45_sub_5 _ _ _ _ hd_ab hd_xy hle

end Problems.sylvester_gallai
