import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- A finite set covered by a nonempty chain union lies entirely within some single chain member.
theorem s18_s4_main_sub_1_sub_1 : ∀ {α : Type} (c : Set (Set (PropForm α))),
    c.Nonempty →
    IsChain (· ⊆ ·) c →
    ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ c →
    ∃ N ∈ c, T ⊆ N := by
  sorry

end Problems.compactness
