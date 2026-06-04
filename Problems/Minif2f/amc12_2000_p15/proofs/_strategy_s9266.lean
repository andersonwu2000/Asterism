import Mathlib
import Problems.Minif2f.amc12_2000_p15.Defs

namespace Problems.Minif2f.amc12_2000_p15

-- Direct evaluation: rewrite (f⁻¹{7}).toFinset to ({2/3, -1} : Finset ℂ) via Finset.ext + h_set,
-- then expand the insert/singleton sum to (2/3)/3 + (-1)/3 and close with ring.
theorem s9266 (f : ℂ → ℂ) (h₁ : Fintype (f ⁻¹' {7}))
    (h_set : f ⁻¹' {7} = ({2/3, -1} : Set ℂ)) :
    (∑ y ∈ (f ⁻¹' {7}).toFinset, y / 3) = -1 / 9 := by
  have h_finset : (f ⁻¹' {7}).toFinset = ({2/3, -1} : Finset ℂ) := by
    ext x
    simp [h_set]
  rw [h_finset]
  rw [show ({2/3, -1} : Finset ℂ) = insert (2/3 : ℂ) {-1} from rfl]
  rw [Finset.sum_insert (by simp; intro h; norm_num at h)]
  rw [Finset.sum_singleton]
  ring

end Problems.Minif2f.amc12_2000_p15
