import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_gamma_circ_phi_at_one
import Problems.residue_thm.proofs.L_gamma_circ_phi_at_zero
import Problems.residue_thm.proofs.L_gamma_circ_phi_avoidance_unit
import Problems.residue_thm.proofs.L_gamma_circ_phi_contdiffon_unit
import Problems.residue_thm.proofs.L_gamma_circ_phi_derivwithin_zero_at_one
import Problems.residue_thm.proofs.L_gamma_circ_phi_derivwithin_zero_at_zero

namespace Problems.residue_thm

-- Split the 6-conjunct conclusion into six independent sub-goals (one per conjunct):
-- C¹ composition, endpoint identities at 0 and 1, flat-derivWithin at 0 and 1
-- (via the φ-flat-at-endpoint hypothesis), and pointwise avoidance through φrange.
-- Each sub-goal carries only the hypotheses it needs; the parent combines them with
-- `⟨…⟩`. Reduces a tuple goal to strictly simpler component lemmas.
theorem s10591
    {a : ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) ∧
    (γ ∘ φ) 0 = γ 0 ∧
    (γ ∘ φ) 1 = γ 1 ∧
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0 ∧
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0 ∧
    (∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a)  := by
  have h1 : ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) :=
    gamma_circ_phi_contdiffon_unit hγ hφ hφrange
  have h2 : (γ ∘ φ) 0 = γ 0 :=
    gamma_circ_phi_at_zero (γ := γ) hφ0
  have h3 : (γ ∘ φ) 1 = γ 1 :=
    gamma_circ_phi_at_one (γ := γ) hφ1
  have h4 : derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0 :=
    gamma_circ_phi_derivwithin_zero_at_zero hγ hφ hφrange hφd0
  have h5 : derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0 :=
    gamma_circ_phi_derivwithin_zero_at_one hγ hφ hφrange hφd1
  have h6 : ∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a :=
    gamma_circ_phi_avoidance_unit havoid hφrange
  exact ⟨h1, h2, h3, h4, h5, h6⟩

end Problems.residue_thm
