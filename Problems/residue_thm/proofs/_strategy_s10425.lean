import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_kernel_int_local_radii_eq
import Problems.residue_thm.proofs.L_local_radii_nhd_event

namespace Problems.residue_thm

-- Local-radius substitution: near `z₁`, both `z ↦ (dist z z₀ + R)/2` and the constant
-- `(dist z₁ z₀ + R)/2` are valid radii for the kernel `w ↦ f w / (w - z)`, so by
-- annular radius-independence the two circle integrals agree pointwise on a nbhd of z₁.
-- Sub-goal `local_radii_nhd_event` (Builder, metric/topology only): exhibits the nbhd on which
--   `z ∈ ball z₀ R` and `dist z z₀ < (dist z₁ z₀ + R)/2` both hold — pure continuity argument.
-- Sub-goal `kernel_int_local_radii_eq` (Builder, direct sibling call): pointwise radius
--   equality of `∮ w in C(z₀,·), f w / (w - z)` between the two radii on the witness nbhd,
--   bundled as a clean specialization of the proved `cauchy_kernel_circle_int_radius_indep`.
-- Combinator: introduce `z₁`, take the nbhd event, rewrite the per-z integrals via the
-- equality lemma, multiply by `(2πi)⁻¹` via `congr_arg`.
theorem s10425
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z₁ ∈ Metric.ball z₀ R,
      (fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        ∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z)) =ᶠ[nhds z₁]
      fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        ∮ w in C(z₀, (dist z₁ z₀ + R) / 2), f w / (w - z) := by
  intro z₁ hz₁
  have h_nbhd := local_radii_nhd_event hR hf z₁ hz₁
  have h_eq := kernel_int_local_radii_eq hR hf z₁ hz₁
  filter_upwards [h_nbhd] with z hz
  obtain ⟨hzball, hzd⟩ := hz
  exact congrArg ((2 * (Real.pi : ℂ) * Complex.I)⁻¹ * ·) (h_eq z hzball hzd)

end Problems.residue_thm
