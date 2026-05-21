import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct one-step proof per lesson 34: compose joint `HasFDerivWithinAt` with the
-- `t' ↦ (τ, t')` section's `HasDerivWithinAt (0,1)`, then `.derivWithin` against
-- `uniqueDiffOn_Icc_zero_one`. No sub-goals required (framework leaf-bypass).
theorem s10398
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      derivWithin (H τ) (Set.Icc (0:ℝ) 1) t =
        fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) ((0:ℝ), (1:ℝ))  := by
  intro τ hτ t ht
  have hpt : (τ, t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 := Set.mk_mem_prod hτ ht
  have hfderiv : HasFDerivWithinAt (fun q : ℝ × ℝ => H q.1 q.2)
      (fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
    (hH.differentiableOn (by norm_num) _ hpt).hasFDerivWithinAt
  have hsection : HasDerivWithinAt (fun t' : ℝ => (τ, t')) ((0:ℝ), (1:ℝ))
      (Set.Icc (0:ℝ) 1) t :=
    (hasDerivWithinAt_const t _ τ).prodMk (hasDerivWithinAt_id t _)
  have hmaps : Set.MapsTo (fun t' : ℝ => (τ, t')) (Set.Icc (0:ℝ) 1)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    fun t' ht' => Set.mk_mem_prod hτ ht'
  exact (hfderiv.comp_hasDerivWithinAt t hsection hmaps).derivWithin
    (uniqueDiffOn_Icc_zero_one t ht)

end Problems.residue_thm
