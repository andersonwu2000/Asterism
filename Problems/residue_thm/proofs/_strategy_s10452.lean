import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_remainder_principal_part_decomp
import Problems.residue_thm.proofs.L_cauchy_path_integral_analytic_simply_connected
import Problems.residue_thm.proofs.L_principal_part_winding_residue_formula

namespace Problems.residue_thm

-- Principal-part decomposition route (strategist-directive).
-- Three sub-goals:
--  (1) `analytic_remainder_principal_part_decomp` — split f globally on U\T as
--      `g + ∑ P_a` with `g` analytic on U, each `P_a` analytic on `ℂ \ {a}` and
--      tending to 0 at ∞, residue equality `residue (P a) a = residue f a`, and
--      the integral identity `∫f·γ' = ∫g·γ' + ∑ ∫P_a·γ'`.
--  (2) `cauchy_path_integral_analytic_simply_connected` — analytic remainder
--      vanishes: ∫g·γ' = 0 for `g` analytic on simply-connected open `U`,
--      `γ` a closed C¹ loop in `U`. (Built via `homotopy_invariant_contour_integral`
--      + null-homotopy of `γ` in simply-connected `U`.)
--  (3) `principal_part_winding_residue_formula` — per-pole contour integral:
--      ∫P·γ' = 2πi·windingNumber γ a · residue P a, for `P` analytic on `ℂ\{a}`
--      tending to 0 at ∞, `γ` closed C¹ avoiding `a`.
-- Combinator: apply (1) to split, rewrite the analytic-remainder integral via
-- (2) to 0, rewrite each pole integral via (3), then `Finset.mul_sum` + `ring`.
theorem s10452 : ∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a  := by
  intro U T f γ hU hSC hT hf hγ hmaps hclosed
  have h_avoid : ∀ a ∈ T, ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a := by
    intro a ha t ht
    intro heq
    exact (hmaps ht).2 (heq ▸ (Finset.mem_coe.mpr ha))
  have h_decomp := analytic_remainder_principal_part_decomp hU hT hf hγ hmaps
  obtain ⟨g, P, hg_an, hP_an, hP_tend, hP_res, h_int_eq⟩ := h_decomp
  have h_g_zero : (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 :=
    cauchy_path_integral_analytic_simply_connected hU hSC hg_an hγ
      (hmaps.mono_right Set.diff_subset) hclosed
  have h_P_each : ∀ a ∈ T,
      (∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t) =
        2 * Real.pi * Complex.I *
          ((Complex.windingNumber γ a : ℂ) * Complex.residue f a) := by
    intro a ha
    have hPa := principal_part_winding_residue_formula
      (hP_an a ha) (hP_tend a ha) hγ (h_avoid a ha) hclosed
    rw [hPa, hP_res a ha]
  rw [h_int_eq, h_g_zero, zero_add, Finset.mul_sum]
  exact Finset.sum_congr rfl (fun a ha => h_P_each a ha)

end Problems.residue_thm
