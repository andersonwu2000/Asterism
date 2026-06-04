import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_image_card_eq
import Problems.Minif2f.imo_1978_p5.proofs.L_image_ge_one
import Problems.Minif2f.imo_1978_p5.proofs.L_sum_eq_image_sum

namespace Problems.Minif2f.imo_1978_p5

-- Split the parent's 3-way conjunction into one sub-goal per conjunct.
-- (1) image_card_eq: cardinality of the image equals m (uses injectivity).
-- (2) image_ge_one: every image element is ≥ 1 (uses a 0 = 0 + injectivity).
-- (3) sum_eq_image_sum: Σ a k = Σ over image (Finset.sum_image, injective).
-- Combinator is the anonymous constructor ⟨_, _, _⟩ for the And-conjunction.
theorem s9593 :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    ((Finset.Icc 1 m).image a).card = m ∧
      (∀ x ∈ (Finset.Icc 1 m).image a, 1 ≤ x) ∧
      (∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) =
        ∑ x ∈ (Finset.Icc 1 m).image a, (x : ℝ)  := by
  intro n a hinj h0 m hm
  have h_card := image_card_eq n a hinj h0 m hm
  have h_pos := image_ge_one n a hinj h0 m hm
  have h_sum := sum_eq_image_sum n a hinj h0 m hm
  exact ⟨h_card, h_pos, h_sum⟩

end Problems.Minif2f.imo_1978_p5
