import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_intvl_integrable_continuous_circ_c1

namespace Problems.residue_thm

-- Reduce to a single continuity-only sub-goal. Since `g` is analytic on the
-- open set `U`, it is continuous on `U` (`AnalyticOn.continuousOn`), and `γ`
-- maps `Icc 0 1` into `U \ T ⊆ U`. The remaining work — that
-- `(g ∘ γ) * γ'` is interval-integrable on `0..1` whenever `g` is
-- ContinuousOn `U` and `γ` is `ContDiffOn ℝ 1 γ (Icc 0 1)` mapping into `U` —
-- is the abstracted Builder sub-goal `intvl_integrable_continuous_circ_c1`
-- (no antiderivative is needed: the proof goes through
-- `ContinuousOn.intervalIntegrable_of_Icc` on the `derivWithin` version and
-- `congr_ae` to switch back to `deriv γ`, à la the proved sibling
-- `interval_integrable_integrand`).
theorem s10460
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ)
    (hg : AnalyticOn ℂ g U)
    (hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}))
    (hpw : ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) :
    IntervalIntegrable (fun t => g (γ t) * deriv γ t) MeasureTheory.volume 0 1  := by
  have h_g_cont : ContinuousOn g U := hg.continuousOn
  have h_maps_U : Set.MapsTo γ (Set.Icc 0 1) U :=
    hmaps.mono_right Set.diff_subset
  exact intvl_integrable_continuous_circ_c1 h_g_cont hγ h_maps_U

end Problems.residue_thm
