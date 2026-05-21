import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_chooser_avoiding_singularity
import Problems.residue_thm.proofs.L_path_diff_eq_connector

namespace Problems.residue_thm

-- Construct F via path integration: pick a basepoint z₀ ≠ a together with a
-- chooser ψ : ℂ → (ℝ → ℂ) giving, for every z ≠ a, a C¹ path in ℂ \ {a} from
-- z₀ to z (sub-goal `path_chooser_avoiding_singularity`). Define F z to be the
-- path integral of Q along that chosen path. For any test path γ avoiding a,
-- F(γ 1) - F(γ 0) reduces to the difference of integrals over the two chosen
-- paths α := ψ(γ 0), β := ψ(γ 1); the sub-goal `path_diff_eq_connector`
-- packages the closed-loop argument (α · γ · β⁻¹ is a C¹ loop avoiding a, so
-- h_loops kills its integral) that turns that difference into the integral
-- along γ.  Both sub-goals receive the full parent hypothesis package.
theorem s10497
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0) :
    ∃ F : ℂ → ℂ, ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t  := by
  have h_chooser := path_chooser_avoiding_singularity hQ_an h_loops
  have h_connector := @path_diff_eq_connector _ _ hQ_an h_loops
  obtain ⟨z₀, ψ, hz0_ne, hψ⟩ := h_chooser
  refine ⟨fun z => ∫ t in (0:ℝ)..1, Q (ψ z t) * deriv (ψ z) t, ?_⟩
  intro γ hγ hγ_avoid
  have hγ0_ne : γ 0 ≠ a := hγ_avoid 0 (Set.left_mem_Icc.mpr zero_le_one)
  have hγ1_ne : γ 1 ≠ a := hγ_avoid 1 (Set.right_mem_Icc.mpr zero_le_one)
  obtain ⟨hα_smooth, hα0, hα1, hα_avoid⟩ := hψ (γ 0) hγ0_ne
  obtain ⟨hβ_smooth, hβ0, hβ1, hβ_avoid⟩ := hψ (γ 1) hγ1_ne
  exact h_connector hα_smooth hα_avoid hβ_smooth hβ_avoid hγ hγ_avoid
    (hα0.trans hβ0.symm) hα1 hβ1

end Problems.residue_thm
