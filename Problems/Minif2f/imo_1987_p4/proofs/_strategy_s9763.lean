import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs.L_even_nonfixed_card

namespace Problems.Minif2f.imo_1987_p4

-- Parity counting: the non-fixed-point set is closed under the involution g and
-- contains no fixed point, so g pairs its elements ⇒ even cardinality (sub-goal).
-- Combined with 1987 odd and the filter-split #(g a = a) + #(g a ≠ a) = 1987,
-- the fixed-point filter has odd (hence positive) card, giving the witness.
theorem s9763 :
    ∀ (g : ℕ → ℕ), (∀ a, a < 1987 → g a < 1987) →
      (∀ a, a < 1987 → g (g a) = a) →
      ∃ a, a < 1987 ∧ g a = a  := by
  intro g hg hgg

  have h_even := even_nonfixed_card g hg hgg

  -- 1987 = #{a | g a = a} + #{a | g a ≠ a}; LHS odd ⇒ #fixed odd ⇒ > 0
  have hsplit :
      (Finset.filter (fun a => g a = a) (Finset.range 1987)).card
        + (Finset.filter (fun a => g a ≠ a) (Finset.range 1987)).card
        = 1987 := by
    have := Finset.card_filter_add_card_filter_not
      (s := Finset.range 1987) (p := fun a => g a = a)
    simpa using this
  have hodd : ¬ 2 ∣ (Finset.filter (fun a => g a = a) (Finset.range 1987)).card := by
    intro hd
    obtain ⟨c, hc⟩ := h_even
    obtain ⟨d, hd'⟩ := hd
    omega
  have hpos : 0 < (Finset.filter (fun a => g a = a) (Finset.range 1987)).card := by
    by_contra hle
    interval_cases (Finset.filter (fun a => g a = a) (Finset.range 1987)).card
    · exact hodd ⟨0, rfl⟩
  rcases Finset.card_pos.mp hpos with ⟨a, ha⟩
  rw [Finset.mem_filter, Finset.mem_range] at ha
  exact ⟨a, ha.1, ha.2⟩


end Problems.Minif2f.imo_1987_p4
