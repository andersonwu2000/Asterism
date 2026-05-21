import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_integral_eq_primitive_diff

namespace Problems.residue_thm

-- closed_path_zero_from_punctured_primitive: FTC on ℂ\{a} collapses closed-path
-- integral to F(γ 1) - F(γ 0) = 0 via path_integral_eq_primitive_diff + hclosed.
theorem closed_path_zero_from_punctured_primitive
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {F : ℂ → ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    (hF : ∀ z ∈ Set.univ \ ({a} : Set ℂ),
      HasDerivAt F (P z - Complex.residue P a / (z - a)) z) :
    (∫ t in (0:ℝ)..1, (P (γ t) - Complex.residue P a / (γ t - a)) * deriv γ t) = 0 := by
  have hU : IsOpen (Set.univ \ ({a} : Set ℂ)) := by
    rw [← Set.compl_eq_univ_diff]; exact isOpen_compl_singleton
  have hγU : Set.MapsTo γ (Set.Icc 0 1) (Set.univ \ ({a} : Set ℂ)) := fun t ht =>
    ⟨Set.mem_univ _, h_avoid t ht⟩
  have hftc := path_integral_eq_primitive_diff hU hF hγ hγU
  rw [hftc, ← hclosed, sub_self]

end Problems.residue_thm
