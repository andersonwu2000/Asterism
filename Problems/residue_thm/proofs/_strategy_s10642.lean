import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_comp_deriv_zero_at_interior_boundary
import Problems.residue_thm.proofs.L_phi_deriv_zero_at_interior_boundary

namespace Problems.residue_thm

-- Decomposition (boundary case φ t ∈ {0,1} at interior t ∈ Ioo 0 1):
-- (a) `phi_deriv_zero_at_interior_boundary`: monotonicity + range force φ to be
--     locally constant on a one-sided neighborhood of t, then C¹-continuity of
--     `deriv φ` (no values at t = 0 or t = 1 needed) gives `deriv φ t = 0`.
-- (b) `comp_deriv_zero_at_interior_boundary`: γ is Lipschitz on Icc 0 1 (C¹ on
--     a compact), so the difference-quotient of `γ ∘ φ` at t is bounded by L
--     times that of φ, which vanishes — giving `deriv (γ ∘ φ) t = 0`.
-- Combine via 0 = 0 • _.
theorem s10642
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc (0 : ℝ) 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (hbnd : φ t = 0 ∨ φ t = 1) :
    deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t)  := by
  have h_phi : deriv φ t = 0 :=
    phi_deriv_zero_at_interior_boundary hφ hφrange hφmono ht hbnd
  have h_comp : deriv (γ ∘ φ) t = 0 :=
    comp_deriv_zero_at_interior_boundary hγ hφ hφrange hφmono ht hbnd
  rw [h_phi, h_comp]; exact (zero_smul ℝ _).symm

end Problems.residue_thm
