import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_exists_isolating_radii_for_finset_poles
import Problems.residue_thm.proofs.L_residue_eq_circle_integral
import Problems.residue_thm.proofs.L_path_int_eq_winding_circle_sum

namespace Problems.residue_thm

-- Decompose into (a) the homological Cauchy bridge — `∫_γ f` over γ equals the
-- winding-weighted sum of small-circle integrals around each pole — and (b)
-- the trivial algebraic step turning each circle integral into `2πi · residue`
-- via the proved `residue_eq_circle_integral`. Combinator extracts isolating
-- radii via the proved `exists_isolating_radii_for_finset_poles`, applies (a)
-- to rewrite the LHS, then `Finset.mul_sum` + pointwise (b) + `field_simp` closes.
--
-- Strategist-directive ack: sub-goal (a) IS the homological/cycle-decomposition
-- Cauchy identity that has been ConfirmShelved twice on
-- `cycle_decomposition_into_loops` (2147); it shares the same Mathlib gap
-- (`primitive_exists_on_simply_connected` open TODO; no direct cycle/winding
-- Cauchy in Mathlib). Decomposition here keeps the gap isolated behind one
-- clearly-named sub-goal so a future Forward inject of the simply-connected
-- Cauchy bridge closes `main` without re-decomposition. No novel mechanism is
-- claimed for the analytic core itself — only structural separation of the
-- radii-setup (proved) and the residue↔circle algebra (proved) from the
-- residual gap.
theorem s10406 : ∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a  := by
  intro U T f γ hU hsc hT hf hγ hmaps hclosed
  obtain ⟨r, ρ, hρ_pos, hρ_lt, hr_analytic, hρ_path, hρ_pairwise⟩ :=
    exists_isolating_radii_for_finset_poles hU hT hf hγ.continuousOn hmaps
  have h_winding_sum :
      (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
        ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * ∮ z in C(a, ρ a), f z :=
    path_int_eq_winding_circle_sum hU hsc hT hf hγ hmaps hclosed
      hρ_pos hρ_lt hr_analytic hρ_path hρ_pairwise
  rw [h_winding_sum, Finset.mul_sum]
  refine Finset.sum_congr rfl (fun a ha => ?_)
  have h_res := residue_eq_circle_integral (hr_analytic a ha) (hρ_pos a ha) (hρ_lt a ha)
  rw [h_res]
  field_simp
end Problems.residue_thm
