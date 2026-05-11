import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_kelly_descent_one_pair
import Problems.sylvester_gallai.proofs.L_kelly_pigeon_3_collinear

namespace Problems.sylvester_gallai

-- Decompose Kelly 4-point descent into: (1) a pure pigeon-hole picking two
-- points of {a,b,r} on the same closed side of the foot of c on line ab, with
-- the "closer-to-foot" one identified as u; and (2) the core geometric descent
-- showing that perpendicular distance from u to line (c,v) is strictly less
-- than that from c to line (a,b). Patch chains them and discharges the
-- ¬Collinear and disjunction housekeeping inline.
theorem s383 :
    ∀ a b r c : ℝ × ℝ, Collinear a b r → r ≠ a → r ≠ b → ¬ Collinear a b c →
      ∃ a' b' c' : ℝ × ℝ,
        (a' = a ∨ a' = b ∨ a' = r ∨ a' = c) ∧
        (b' = a ∨ b' = b ∨ b' = r ∨ b' = c) ∧
        (c' = a ∨ c' = b ∨ c' = r ∨ c' = c) ∧
        ¬ Collinear a' b' c' ∧
        ((c'.1 - a'.1) * (b'.2 - a'.2) - (c'.2 - a'.2) * (b'.1 - a'.1))^2 /
            ((b'.1 - a'.1)^2 + (b'.2 - a'.2)^2) <
        ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 /
            ((b.1 - a.1)^2 + (b.2 - a.2)^2)  := by
  intro a b r c hcabr hrna hrnb habc
  obtain ⟨u, v, hu, hv, huv, hsame, hcloser⟩ :=
    kelly_pigeon_3_collinear a b r c hcabr hrna hrnb habc
  have hcu : Collinear a b u := by
    rcases hu with h | h | h
    · rw [h]; unfold Collinear; ring
    · rw [h]; unfold Collinear; ring
    · rw [h]; exact hcabr
  have hcv : Collinear a b v := by
    rcases hv with h | h | h
    · rw [h]; unfold Collinear; ring
    · rw [h]; unfold Collinear; ring
    · rw [h]; exact hcabr
  obtain ⟨hnc, hlt⟩ :=
    kelly_descent_one_pair a b u v c huv hcu hcv habc hsame hcloser
  refine ⟨c, v, u, Or.inr (Or.inr (Or.inr rfl)), ?_, ?_, hnc, hlt⟩
  · rcases hv with h | h | h
    · exact Or.inl h
    · exact Or.inr (Or.inl h)
    · exact Or.inr (Or.inr (Or.inl h))
  · rcases hu with h | h | h
    · exact Or.inl h
    · exact Or.inr (Or.inl h)
    · exact Or.inr (Or.inr (Or.inl h))

end Problems.sylvester_gallai
