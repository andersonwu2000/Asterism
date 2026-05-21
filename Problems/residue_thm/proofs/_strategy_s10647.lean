import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_phi_deriv_zero_at_interior_max_value
import Problems.residue_thm.proofs.L_phi_deriv_zero_at_interior_min_value

namespace Problems.residue_thm

-- Case split on `hbnd : φ t = 0 ∨ φ t = 1`.
-- Each case is the Fermat-extremum argument at an interior point of `Icc 0 1`:
-- if φ t hits the lower (resp. upper) end of the range, t is an interior local
-- min (resp. max), so `deriv φ t = 0` by `IsLocalMin/Max.deriv_eq_zero`.
theorem s10647
    {φ : ℝ → ℝ}
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (hbnd : φ t = 0 ∨ φ t = 1) :
    deriv φ t = 0  := by
  rcases hbnd with h0 | h1
  · exact phi_deriv_zero_at_interior_min_value hφ hφrange hφmono ht h0
  · exact phi_deriv_zero_at_interior_max_value hφ hφrange hφmono ht h1

end Problems.residue_thm
