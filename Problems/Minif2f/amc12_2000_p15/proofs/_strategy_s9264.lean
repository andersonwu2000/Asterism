import Mathlib
import Problems.Minif2f.amc12_2000_p15.Defs
import Problems.Minif2f.amc12_2000_p15.proofs.L_quadratic_root_iff

namespace Problems.Minif2f.amc12_2000_p15

-- Reduce set equality to the scalar quadratic iff via Set.ext + h_char rewriting.
-- Sub-goal `quadratic_root_iff` is the pure arithmetic fact 9y²+3y+1 = 7 ↔ y ∈ {2/3, -1}.
theorem s9264 (f : ℂ → ℂ) (h_char : ∀ y : ℂ, f y = 9 * y^2 + 3 * y + 1) :
    f ⁻¹' {7} = ({2/3, -1} : Set ℂ)  := by
  have h_iff := quadratic_root_iff
  ext y
  simp only [Set.mem_preimage, Set.mem_singleton_iff, h_char y, Set.mem_insert_iff]
  exact h_iff y

end Problems.Minif2f.amc12_2000_p15
