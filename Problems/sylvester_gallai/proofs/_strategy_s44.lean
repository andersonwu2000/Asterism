import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s44_sub_1
import Problems.sylvester_gallai.proofs.L_s44_sub_2
import Problems.sylvester_gallai.proofs.L_s44_sub_3

namespace Problems.sylvester_gallai

theorem s44 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ q ∈ P, p ≠ q ∧ ∀ r ∈ P, Collinear p q r → r = p ∨ r = q  := by
  intro P hP
  obtain ⟨p, hp, a, ha, b, hb, hab, hnc, hmin⟩ := s44_sub_1 P hP
  exact ⟨a, ha, b, hb, hab,
    s44_sub_3 P p a b hp ha hb hab hnc hmin
      (fun p' a' b' c' h1 h2 h3 h4 h5 => s44_sub_2 p' a' b' c' h1 h2 h3 h4 h5)⟩

end Problems.sylvester_gallai
