import Mathlib
import Problems.Minif2f.amc12_2000_p15.Defs
import Problems.Minif2f.amc12_2000_p15.proofs.L_char_f
import Problems.Minif2f.amc12_2000_p15.proofs.L_preimage_seven
import Problems.Minif2f.amc12_2000_p15.proofs.L_sum_over_pair

namespace Problems.Minif2f.amc12_2000_p15

-- Decompose by: (a) characterize f via h₀ substitution x ↦ 3y giving f y = 9y²+3y+1,
-- (b) identify the preimage f⁻¹{7} = {2/3, -1} from the quadratic (3y-2)(y+1)=0,
-- (c) evaluate the sum (2/3)/3 + (-1)/3 = -1/9 on the resolved Finset.
theorem s563 : ∀ (f : ℂ → ℂ) (h₀ : ∀ x, f (x / 3) = x ^ 2 + x + 1)
    (h₁ : Fintype (f ⁻¹' {7})),
    (∑ y ∈ (f ⁻¹' {7}).toFinset, y / 3) = -1 / 9 := by
  intro f h₀ h₁
  have h_char : ∀ y : ℂ, f y = 9 * y^2 + 3 * y + 1 := char_f f h₀
  have h_set : f ⁻¹' {7} = ({2/3, -1} : Set ℂ) := preimage_seven f h_char
  exact sum_over_pair f h₁ h_set

end Problems.Minif2f.amc12_2000_p15
