-- Split the parent's 3-way conjunction into one sub-goal per conjunct.
-- (1) image_card_eq: cardinality of the image equals m (uses injectivity).
-- (2) image_ge_one: every image element is ≥ 1 (uses a 0 = 0 + injectivity).
-- (3) sum_eq_image_sum: Σ a k = Σ over image (Finset.sum_image, injective).
-- Combinator is the anonymous constructor ⟨_, _, _⟩ for the And-conjunction.
import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs._strategy_s9593

namespace Problems.Minif2f.imo_1978_p5

def image_card_pos_eq := @Problems.Minif2f.imo_1978_p5.s9593

end Problems.Minif2f.imo_1978_p5
