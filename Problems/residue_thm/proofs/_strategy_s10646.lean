import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_gamma_lipschitz_on_unit_icc
import Problems.residue_thm.proofs.L_lipschitz_comp_has_deriv_zero
import Problems.residue_thm.proofs.L_phi_deriv_zero_alias

open scoped Topology

namespace Problems.residue_thm

-- Decomposition (Lipschitz + zero-derivative interior strategy):
-- (a) `phi_deriv_zero_alias`: deriv φ t = 0 — sibling-style alias of
--     `phi_deriv_zero_at_interior_boundary` (monotonicity + boundary image).
-- (b) `gamma_lipschitz_on_unit_icc`: γ is Lipschitz on Icc 0 1 (C¹ on a compact).
-- (c) `lipschitz_comp_has_deriv_zero`: abstract — if f is Lipschitz on s,
--     g eventually lives in s near t, and `HasDerivAt g 0 t`, then
--     `HasDerivAt (f ∘ g) 0 t` (no need for f to be differentiable at g t).
-- Combine: build `HasDerivAt (γ ∘ φ) 0 t`, then take `.deriv`.
theorem s10646
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc (0 : ℝ) 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (hbnd : φ t = 0 ∨ φ t = 1) :
    deriv (γ ∘ φ) t = 0  := by
  have h_phi_deriv : deriv φ t = 0 :=
    phi_deriv_zero_alias hφ hφrange hφmono ht hbnd
  have h_phi_hasderiv : HasDerivAt φ 0 t := by
    have h := ((hφ.differentiable one_ne_zero).differentiableAt (x := t)).hasDerivAt
    rwa [h_phi_deriv] at h
  obtain ⟨K, hK⟩ := gamma_lipschitz_on_unit_icc hγ
  have h_phi_eventually : ∀ᶠ s in 𝓝 t, φ s ∈ Set.Icc (0 : ℝ) 1 := by
    have hmem : Set.Ioo (0 : ℝ) 1 ∈ 𝓝 t := isOpen_Ioo.mem_nhds ht
    filter_upwards [hmem] with s hs
    exact hφrange s (Set.Ioo_subset_Icc_self hs)
  have h_comp_hasderiv : HasDerivAt (γ ∘ φ) 0 t :=
    lipschitz_comp_has_deriv_zero hK h_phi_eventually h_phi_hasderiv
  exact h_comp_hasderiv.deriv


end Problems.residue_thm
