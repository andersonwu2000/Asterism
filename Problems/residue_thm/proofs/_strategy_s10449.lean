import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integral_split_along_closed_path
import Problems.residue_thm.proofs.L_residue_global_principal_part_decomp

namespace Problems.residue_thm

-- Split into (1) construction of the global decomposition `f = g + ∑ P_a` on
-- `U \ T` with `g` analytic on `U`, each `P_a` analytic on `ℂ \ {a}` tending to
-- 0 at infinity and matching `f`'s residue at `a` (no path involved), and
-- (2) lifting that pointwise identity to the integral identity along `γ`.
-- Combinator: feed the path-side hypotheses from (1) into (2).
theorem s10449
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a})) ∧
      (∀ a ∈ T, Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0)) ∧
      (∀ a ∈ T, Complex.residue (P a) a = Complex.residue f a) ∧
      (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
        (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) +
        ∑ a ∈ T, ∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t  := by
  obtain ⟨g, P, hg, hP_ana, hP_tendsto, hP_residue, hpoint⟩ :=
    residue_global_principal_part_decomp hU hT hf
  refine ⟨g, P, hg, hP_ana, hP_tendsto, hP_residue, ?_⟩
  exact integral_split_along_closed_path hg hP_ana hγ hmaps hpoint

end Problems.residue_thm
