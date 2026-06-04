import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_image_triple_card_48
import Problems.Minif2f.amc12a_2020_p21.proofs.L_image_triple_mem_iff

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: exhibit the witness Finset as the image of the triple
-- product `Icc 3 8 ×ˢ Icc 1 4 ×ˢ Icc 0 1` under `(a,b,d) ↦ 2^a · 3^b · 5^3 · 7^d`.
-- Sub-goal `image_triple_card_48` handles the cardinality (image of an injective
-- map on a product of card 6·4·2 = 48). Sub-goal `image_triple_mem_iff` handles
-- the substantive arithmetic: forcing n into the parametrised form using the
-- valuations lcm(5!, n) = 5 · gcd(10!, n) together with 5 ∣ n. Combinator is the
-- existential introduction with the two pieces.
theorem s9462 :
    ∃ T : Finset ℕ, T.card = 48 ∧
      ∀ n : ℕ, n ∈ T ↔ 5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n  := by
  have h_card := image_triple_card_48
  have h_mem := image_triple_mem_iff
  exact ⟨_, h_card, h_mem⟩

end Problems.Minif2f.amc12a_2020_p21
