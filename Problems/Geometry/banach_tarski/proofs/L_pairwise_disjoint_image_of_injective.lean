import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- pairwise_disjoint_image_of_injective: injective image preserves pairwise-disjoint families
-- (f i = ψ '' g i, ψ injective, g pairwise-disjoint on s) → f pairwise-disjoint on s
theorem pairwise_disjoint_image_of_injective {G K : Type*} (ψ : G → K)
    (hψ : Function.Injective ψ) {ι : Type*} (s : Set ι) (g : ι → Set G)
    (f : ι → Set K) (hf : ∀ i, f i = ψ '' g i) (hg : s.PairwiseDisjoint g) :
    s.PairwiseDisjoint f := by
  intro i hi j hj hij
  unfold Function.onFun; rw [hf i, hf j]
  rw [Set.disjoint_left]
  rintro x ⟨a, ha, rfl⟩ ⟨b, hb, hbeq⟩
  have hab : a = b := hψ hbeq.symm
  subst hab
  exact Set.disjoint_left.mp (hg hi hj hij) ha hb

end Problems.Geometry.banach_tarski
