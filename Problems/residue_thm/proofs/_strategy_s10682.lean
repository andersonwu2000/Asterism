import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_piecewise_split_eq_pointwise_on_ioo

namespace Problems.residue_thm

-- Reduce eventually-equal-on-nhds to pointwise equality on the open neighborhood Ioo (1/2) 1.
-- Sub-goal piecewise_split_eq_pointwise_on_ioo provides the pointwise equality on Ioo (1/2) 1;
-- isOpen_Ioo.mem_nhds ht supplies Ioo (1/2) 1 ∈ nhds t, closing via Filter.eventuallyEq_of_mem.
theorem s10682
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      (fun u : ℝ => α' 0 + ∫ s in (0:ℝ)..u,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        =ᶠ[nhds t]
        (fun u : ℝ => (α' 0 + ∫ s in (0:ℝ)..((1:ℝ)/2),
                  2 * derivWithin α' (Set.Icc 0 1) (2*s)) +
          ∫ s in ((1:ℝ)/2)..u, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))  := by
  intro t ht
  have h_pt := piecewise_split_eq_pointwise_on_ioo hα' hβ'
  exact (Filter.eventuallyEq_of_mem (isOpen_Ioo.mem_nhds ht) h_pt)

end Problems.residue_thm
