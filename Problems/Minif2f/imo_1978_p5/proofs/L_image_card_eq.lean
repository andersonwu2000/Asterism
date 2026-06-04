import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- image_card_eq: card of image of Finset.Icc 1 m under injective a equals m
-- Uses Finset.card_image_of_injective to reduce to Nat.card_Icc.
theorem image_card_eq :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    ((Finset.Icc 1 m).image a).card = m := by
  intro n a ha ha0 m hm
  rw [Finset.card_image_of_injective _ ha]
  simp [Nat.card_Icc]

end Problems.Minif2f.imo_1978_p5
