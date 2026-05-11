import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- kelly_pigeon_3_collinear: pigeonhole — among 3 collinear projections, two share sign
-- and the smaller-square one can serve as u, the larger as v.
theorem kelly_pigeon_3_collinear :
    ∀ a b r c : ℝ × ℝ, Collinear a b r → r ≠ a → r ≠ b → ¬ Collinear a b c →
      ∃ u v : ℝ × ℝ,
        (u = a ∨ u = b ∨ u = r) ∧ (v = a ∨ v = b ∨ v = r) ∧ u ≠ v ∧
        ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) *
            ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)) ≥ 0 ∧
        ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) ^ 2 ≤
            ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)) ^ 2 := by
  intro a b r c hcol_abr hr_ne_a hr_ne_b hnot_col
  by_cases hab : a = b
  · exfalso; apply hnot_col; subst hab; unfold Collinear; ring
  rcases le_or_gt 0 ((a.1 - c.1) * (b.1 - a.1) + (a.2 - c.2) * (b.2 - a.2)) with ha | ha
  · rcases le_or_gt 0 ((b.1 - c.1) * (b.1 - a.1) + (b.2 - c.2) * (b.2 - a.2)) with hb | hb
    · rcases le_or_gt (((a.1 - c.1) * (b.1 - a.1) + (a.2 - c.2) * (b.2 - a.2)) ^ 2)
                      (((b.1 - c.1) * (b.1 - a.1) + (b.2 - c.2) * (b.2 - a.2)) ^ 2) with hle | hlt
      · exact ⟨a, b, Or.inl rfl, Or.inr (Or.inl rfl), hab, mul_nonneg ha hb, hle⟩
      · exact ⟨b, a, Or.inr (Or.inl rfl), Or.inl rfl, Ne.symm hab, mul_nonneg hb ha, le_of_lt hlt⟩
    · rcases le_or_gt 0 ((r.1 - c.1) * (b.1 - a.1) + (r.2 - c.2) * (b.2 - a.2)) with hr | hr
      · rcases le_or_gt (((a.1 - c.1) * (b.1 - a.1) + (a.2 - c.2) * (b.2 - a.2)) ^ 2)
                        (((r.1 - c.1) * (b.1 - a.1) + (r.2 - c.2) * (b.2 - a.2)) ^ 2) with hle | hlt
        · exact ⟨a, r, Or.inl rfl, Or.inr (Or.inr rfl), Ne.symm hr_ne_a, mul_nonneg ha hr, hle⟩
        · exact ⟨r, a, Or.inr (Or.inr rfl), Or.inl rfl, hr_ne_a, mul_nonneg hr ha, le_of_lt hlt⟩
      · rcases le_or_gt (((b.1 - c.1) * (b.1 - a.1) + (b.2 - c.2) * (b.2 - a.2)) ^ 2)
                        (((r.1 - c.1) * (b.1 - a.1) + (r.2 - c.2) * (b.2 - a.2)) ^ 2) with hle | hlt
        · exact ⟨b, r, Or.inr (Or.inl rfl), Or.inr (Or.inr rfl), Ne.symm hr_ne_b,
                  (mul_pos_of_neg_of_neg hb hr).le, hle⟩
        · exact ⟨r, b, Or.inr (Or.inr rfl), Or.inr (Or.inl rfl), hr_ne_b,
                  (mul_pos_of_neg_of_neg hr hb).le, le_of_lt hlt⟩
  · rcases le_or_gt 0 ((b.1 - c.1) * (b.1 - a.1) + (b.2 - c.2) * (b.2 - a.2)) with hb | hb
    · rcases le_or_gt 0 ((r.1 - c.1) * (b.1 - a.1) + (r.2 - c.2) * (b.2 - a.2)) with hr | hr
      · rcases le_or_gt (((b.1 - c.1) * (b.1 - a.1) + (b.2 - c.2) * (b.2 - a.2)) ^ 2)
                        (((r.1 - c.1) * (b.1 - a.1) + (r.2 - c.2) * (b.2 - a.2)) ^ 2) with hle | hlt
        · exact ⟨b, r, Or.inr (Or.inl rfl), Or.inr (Or.inr rfl), Ne.symm hr_ne_b,
                  mul_nonneg hb hr, hle⟩
        · exact ⟨r, b, Or.inr (Or.inr rfl), Or.inr (Or.inl rfl), hr_ne_b,
                  mul_nonneg hr hb, le_of_lt hlt⟩
      · rcases le_or_gt (((a.1 - c.1) * (b.1 - a.1) + (a.2 - c.2) * (b.2 - a.2)) ^ 2)
                        (((r.1 - c.1) * (b.1 - a.1) + (r.2 - c.2) * (b.2 - a.2)) ^ 2) with hle | hlt
        · exact ⟨a, r, Or.inl rfl, Or.inr (Or.inr rfl), Ne.symm hr_ne_a,
                  (mul_pos_of_neg_of_neg ha hr).le, hle⟩
        · exact ⟨r, a, Or.inr (Or.inr rfl), Or.inl rfl, hr_ne_a,
                  (mul_pos_of_neg_of_neg hr ha).le, le_of_lt hlt⟩
    · rcases le_or_gt (((a.1 - c.1) * (b.1 - a.1) + (a.2 - c.2) * (b.2 - a.2)) ^ 2)
                      (((b.1 - c.1) * (b.1 - a.1) + (b.2 - c.2) * (b.2 - a.2)) ^ 2) with hle | hlt
      · exact ⟨a, b, Or.inl rfl, Or.inr (Or.inl rfl), hab,
                (mul_pos_of_neg_of_neg ha hb).le, hle⟩
      · exact ⟨b, a, Or.inr (Or.inl rfl), Or.inl rfl, Ne.symm hab,
                (mul_pos_of_neg_of_neg hb ha).le, le_of_lt hlt⟩

end Problems.sylvester_gallai
