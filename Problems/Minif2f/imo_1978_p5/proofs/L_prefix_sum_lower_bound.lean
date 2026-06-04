-- Decomposition:
-- (A) `image_card_pos_eq`: the image `(Icc 1 m).image a` has `card = m`, every
--     element is `≥ 1` (since `a 0 = 0` + `a` injective ⇒ no element is `0`),
--     and `∑ k ∈ Icc 1 m, a k = ∑ x ∈ image, x` (via `Finset.sum_image`).
-- (B) `arith_le_distinct_pos_sum`: pure arithmetic fact — any finset of `m`
--     positive naturals has sum ≥ `1 + 2 + ⋯ + m`. No reference to `a`.
-- Combinator rewrites the RHS via the equality in (A), then applies (B) to
-- the image set.
import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs._strategy_s9435

namespace Problems.Minif2f.imo_1978_p5

def prefix_sum_lower_bound := @Problems.Minif2f.imo_1978_p5.s9435

end Problems.Minif2f.imo_1978_p5
