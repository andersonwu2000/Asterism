import Mathlib
import Problems.Minif2f.amc12a_2002_p1.Defs

namespace Problems.Minif2f.amc12a_2002_p1

-- Show (f ⁻¹' {0}).toFinset = {-3/2, 5} via set extensionality from the
-- root-equivalence hypothesis, then compute -3/2 + 5 = 7/2 by ring.
theorem s532 : ∀ (f : ℂ → ℂ) (h₁ : Fintype (f ⁻¹' {0})),
    (∀ x : ℂ, f x = 0 ↔ x = -3/2 ∨ x = 5) →
    (∑ y ∈ (f ⁻¹' {0}).toFinset, y) = 7 / 2  := by
  intro f _ h
  have hfin : (f ⁻¹' {0}).toFinset = ({-3/2, 5} : Finset ℂ) := by
    ext x
    simp [Set.mem_toFinset, Set.mem_preimage, h x,
      Finset.mem_insert, Finset.mem_singleton]
  rw [hfin, show ({-3/2, 5} : Finset ℂ) = insert (-3/2 : ℂ) {5} from rfl,
      Finset.sum_insert (by simp; norm_num), Finset.sum_singleton]
  ring

end Problems.Minif2f.amc12a_2002_p1
