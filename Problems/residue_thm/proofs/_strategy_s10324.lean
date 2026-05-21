import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_exists_isolating_radii_for_finset_poles
import Problems.residue_thm.proofs.L_integral_eq_winding_sum_loops

namespace Problems.residue_thm

-- Extract isolating outer/inner radii from `exists_isolating_radii_for_finset_poles`
-- (sibling lemma packing outer-radius analyticity, inner-positivity, ρ < r, path
-- disjointness, and pairwise disjointness). The first three conjuncts of the
-- conclusion then come for free; the residual integral equality — the
-- homological/multi-pole Cauchy step — is the single sub-goal
-- `integral_eq_winding_sum_loops`, which receives the full radii data plus the
-- parent's hypotheses (in particular `hclosed : γ 0 = γ 1` and the
-- simply-connected ambient `U`).
theorem s10324
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1) :
    ∃ r ρ : ℂ → ℝ,
      (∀ a ∈ T, 0 < ρ a) ∧
      (∀ a ∈ T, ρ a < r a) ∧
      (∀ a ∈ T, AnalyticOn ℂ f (Metric.ball a (r a) \ {a})) ∧
      (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
        ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * ∮ z in C(a, ρ a), f z  := by
  obtain ⟨r, ρ, hρ_pos, hρ_lt, hr_analytic, hρ_path, hρ_pairwise⟩ :=
    exists_isolating_radii_for_finset_poles hU hT hf hγ.continuousOn hmaps
  have h_integral := integral_eq_winding_sum_loops hU hsc hT hf hγ hmaps hclosed
    hρ_pos hρ_lt hr_analytic hρ_path hρ_pairwise
  exact ⟨r, ρ, hρ_pos, hρ_lt, hr_analytic, h_integral⟩

end Problems.residue_thm
