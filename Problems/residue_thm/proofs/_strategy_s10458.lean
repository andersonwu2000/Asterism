import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_pointwise_pole_principal_data

namespace Problems.residue_thm

-- Skolemise the per-pole data: prove `∀ a ∈ T, ∃ (r, Pₐ, hₐ)` carrying the
-- isolating-radius + principal-part decomposition pointwise, then promote via
-- `Classical.choose` (the `choose` tactic) to global functions `P, R, h` and
-- exhibit the parent existential. The single sub-goal is strictly simpler — it
-- drops the global-function coherence requirement, leaving only the local
-- combination of (a) an isolating ball around each pole inside `U` separated
-- from the other elements of `T`, and (b) one application of the already-proved
-- `principal_part_extraction_at_singularity` toolkit lemma to the punctured ball.
theorem s10458
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ (P : ℂ → ℂ → ℂ) (R : ℂ → ℝ) (h : ℂ → ℂ → ℂ),
      ∀ a ∈ T,
        0 < R a ∧
        Metric.ball a (R a) ⊆ U ∧
        (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a (R a)) ∧
        AnalyticOn ℂ (P a) (Set.univ \ {a}) ∧
        Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) ∧
        AnalyticOn ℂ (h a) (Metric.ball a (R a)) ∧
        (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z)  := by
  have h_pw :
      ∀ a : ℂ, ∃ (r : ℝ) (P_a h_a : ℂ → ℂ),
        a ∈ T →
        (0 < r ∧
         Metric.ball a r ⊆ U ∧
         (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a r) ∧
         AnalyticOn ℂ P_a (Set.univ \ {a}) ∧
         Filter.Tendsto P_a (Filter.cocompact ℂ) (nhds 0) ∧
         AnalyticOn ℂ h_a (Metric.ball a r) ∧
         (∀ z ∈ Metric.ball a r \ {a}, f z = h_a z + P_a z)) :=
    pointwise_pole_principal_data hU hT hf
  classical
  choose R P h hcond using h_pw
  exact ⟨P, R, h, fun a ha => hcond a ha⟩

end Problems.residue_thm
