import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- chain_rule_interior: chain rule F∘γ has derivative f(γ t)·γ'(t) at interior points
-- Uses ContDiffOn→DifferentiableAt via Icc_mem_nhds, then HasDerivAt.comp.
theorem chain_rule_interior
    {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ∀ z ∈ U, HasDerivAt F (f z) z)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U) :
    ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun s => F (γ s)) (f (γ t) * deriv γ t) t := by
    intro t ht
    have htIcc : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
    have hγU_t : γ t ∈ U := hγU htIcc
    have hF_t : HasDerivAt F (f (γ t)) (γ t) := hF (γ t) hγU_t
    have hIcc_nhds : Set.Icc (0:ℝ) 1 ∈ nhds t := Icc_mem_nhds ht.1 ht.2
    have hDiff : DifferentiableAt ℝ γ t :=
      (hγC1.differentiableOn (by norm_num)).differentiableAt hIcc_nhds
    exact hF_t.comp t hDiff.hasDerivAt

end Problems.residue_thm
