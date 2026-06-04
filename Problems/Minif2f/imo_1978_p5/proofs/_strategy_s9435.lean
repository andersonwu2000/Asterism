import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_arith_le_distinct_pos_sum
import Problems.Minif2f.imo_1978_p5.proofs.L_image_card_pos_eq

namespace Problems.Minif2f.imo_1978_p5

-- Decomposition:
-- (A) `image_card_pos_eq`: the image `(Icc 1 m).image a` has `card = m`, every
--     element is `≥ 1` (since `a 0 = 0` + `a` injective ⇒ no element is `0`),
--     and `∑ k ∈ Icc 1 m, a k = ∑ x ∈ image, x` (via `Finset.sum_image`).
-- (B) `arith_le_distinct_pos_sum`: pure arithmetic fact — any finset of `m`
--     positive naturals has sum ≥ `1 + 2 + ⋯ + m`. No reference to `a`.
-- Combinator rewrites the RHS via the equality in (A), then applies (B) to
-- the image set.
theorem s9435 :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ k ∈ Finset.Icc 1 m, (a k : ℝ)  := by
  intro n a ha h0 m hm
  have hA := image_card_pos_eq n a ha h0 m hm
  have hB := arith_le_distinct_pos_sum n a ha h0 m hm
  obtain ⟨hcard, hpos, heq⟩ := hA
  rw [heq]
  exact hB _ hcard hpos

end Problems.Minif2f.imo_1978_p5
