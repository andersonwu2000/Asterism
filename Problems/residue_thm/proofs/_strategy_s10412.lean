import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_inner_part_value_implies_analytic
import Problems.residue_thm.proofs.L_inner_part_value_implies_tendsto_zero
import Problems.residue_thm.proofs.L_inner_part_value_witness

namespace Problems.residue_thm

-- Split the conjunctive existential by isolating the value equation from the
-- analyticity / tendsto conjuncts. Sub-goal 1 produces any P satisfying the
-- pointwise integral identity (radii-independent witness). Sub-goals 2 and 3
-- take such a P as hypothesis and derive analyticity on `ℂ \ {z₀}` and decay
-- at cocompact respectively. Each sub-goal drops two of the three conjuncts,
-- so each is strictly simpler than the parent ∃-conjunction.
theorem s10412
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (P : ℂ → ℂ), AnalyticOn ℂ P (Set.univ \ {z₀}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))  := by
  obtain ⟨P, hP_eq⟩ := inner_part_value_witness hR hf
  refine ⟨P, ?_, ?_, hP_eq⟩
  · exact inner_part_value_implies_analytic hR hf P hP_eq
  · exact inner_part_value_implies_tendsto_zero hR hf P hP_eq

end Problems.residue_thm
