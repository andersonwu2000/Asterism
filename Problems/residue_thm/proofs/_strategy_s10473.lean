import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_remainder_path_integral_zero
import Problems.residue_thm.proofs.L_principal_part_split_wrapper
import Problems.residue_thm.proofs.L_principal_part_winding_residue_step

namespace Problems.residue_thm

-- Principal-part decomposition route (strategist directive): split `f` on `U \ T` as
-- `g + ∑ P_a` via the already-proved `analytic_remainder_principal_part_decomp`
-- (wrapped as a Builder sub-goal so the framework auto-imports it — direct
-- citation of a proved sibling fails lake build per LESSONS line 26), vanish the
-- analytic remainder integral, and apply the per-pole winding-residue formula.
-- Sub-goals:
--  (1) `principal_part_split_wrapper` (Builder, leaf wrapper) — re-exports the
--      proved `analytic_remainder_principal_part_decomp` (s10453).
--  (2) `analytic_remainder_path_integral_zero` — for `g` analytic on the
--      simply-connected open `U`, closed C¹ `γ` in `U`:
--      `∫₀¹ g(γ t)·γ'(t) dt = 0`. (Approach hint: compactness of `γ([0,1])` +
--      finite ball cover ⊂ `U` + per-ball `closed_path_integral_zero_on_ball`
--      after subdivision, sidestepping the C² null-homotopy obstruction.)
--  (3) `principal_part_winding_residue_step` — for `P` analytic on `ℂ \ {a}`
--      with `P → 0` at cocompact, closed C¹ `γ` avoiding `a`:
--      `∫₀¹ P(γ t)·γ'(t) dt = 2πi · (windingNumber γ a) · residue P a`.
-- Combinator: apply (1) for the integral split, rewrite the remainder integral via
-- (2), rewrite each pole integral via (3), then use `residue (P a) a = residue f a`
-- from (1) and `Finset.mul_sum` to assemble the right-hand side.
theorem s10473 : ∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a  := by
  intro U T f γ hU hSC hT hf hγ hmaps hclosed
  have h_split := principal_part_split_wrapper hU hT hf hγ hmaps
  obtain ⟨g, P, hg, hPa, hPt, hres, hint_split⟩ := h_split
  have hmaps_U : Set.MapsTo γ (Set.Icc 0 1) U :=
    hmaps.mono_right Set.diff_subset
  have h_avoid : ∀ a ∈ T, ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a := by
    intro a ha t ht hγta
    have hmem := hmaps ht
    exact hmem.2 (hγta ▸ ha)
  have h_g_zero : (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 :=
    analytic_remainder_path_integral_zero hU hSC hg hγ hmaps_U hclosed
  have h_P_each : ∀ a ∈ T,
      (∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t) =
        2 * Real.pi * Complex.I *
          ((Complex.windingNumber γ a : ℂ) * Complex.residue (P a) a) :=
    fun a ha => principal_part_winding_residue_step (hPa a ha) (hPt a ha) hγ (h_avoid a ha) hclosed

  rw [hint_split, h_g_zero, zero_add, Finset.mul_sum]
  refine Finset.sum_congr rfl ?_
  intro a ha
  rw [h_P_each a ha, hres a ha]



end Problems.residue_thm

