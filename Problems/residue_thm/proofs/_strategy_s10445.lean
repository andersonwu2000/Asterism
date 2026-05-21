import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_on_simply_connected_closed_path
import Problems.residue_thm.proofs.L_principal_part_contour_integral_formula
import Problems.residue_thm.proofs.L_residue_principal_part_split

namespace Problems.residue_thm

-- Strategist-directive route: extract principal parts at every pole via
-- `principal_part_extraction_at_singularity` and bundle into a global decomposition
-- `f = g + ∑_{a∈T} P_a` on `U \ T`, where `g` extends analytically to all of the
-- simply-connected `U` and each `P_a` is analytic on `ℂ \ {a}` tending to 0 at
-- infinity. Three sub-goals:
--   (1) `residue_principal_part_split` — existence of `g, P` with the decomposition
--       AND the integral identity `∫_γ f·γ' = ∫_γ g·γ' + ∑_a ∫_γ P_a·γ'` plus
--       `residue (P a) a = residue f a` for each pole.
--   (2) `cauchy_on_simply_connected_closed_path` — Cauchy on simply-connected `U`
--       for closed C¹ paths: `∫_γ g·γ' = 0` whenever `g` is analytic on `U`.
--   (3) `principal_part_contour_integral_formula` — per-pole contour integral of a
--       principal-part-shaped function: `∫_γ P·γ' = 2πi · w(γ,a) · residue P a`.
-- Combinator: apply (1), rewrite remainder via (2), per-pole via (3), then
-- `Finset.mul_sum` + `ring` closes.
theorem s10445 : ∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a  := by
  intro U T f γ hU hSC hT hf hγ hmaps hclosed
  obtain ⟨g, P, hg_an, hP_an, hP_tendsto, hP_res, h_split⟩ :=
    residue_principal_part_split hU hT hf hγ hmaps
  have h_g_zero : (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 :=
    cauchy_on_simply_connected_closed_path hU hSC hg_an hγ
      (hmaps.mono_right Set.diff_subset) hclosed
  rw [h_split, h_g_zero, zero_add, Finset.mul_sum]
  refine Finset.sum_congr rfl (fun a ha => ?_)
  have h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a := by
    intro t ht heq
    have h_in : γ t ∈ U \ ↑T := hmaps ht
    exact h_in.2 (heq ▸ ha)
  have h_pp := principal_part_contour_integral_formula
    (hP_an a ha) (hP_tendsto a ha) hγ h_avoid hclosed
  rw [h_pp, hP_res a ha]
  ring

end Problems.residue_thm
