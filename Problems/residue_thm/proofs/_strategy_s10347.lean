import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_homotopy_partial_tau_continuous_on_ioo

namespace Problems.residue_thm

-- Decompose AEStronglyMeasurable into ContinuousOn on the open interior,
-- then transfer the restrict-measure from `Ioo 0 1` to `uIoc 0 1 = Ioc 0 1`
-- using `Ioo =ᵐ Ioc` (their symmetric difference is `{1}`, a volume-null set).
theorem s10347
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ioo (0:ℝ) 1,
      MeasureTheory.AEStronglyMeasurable
        (fun t => deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) τ)
        (MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) 1))  := by
  intro τ hτ
  have h_cont :
      ContinuousOn (fun t => deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) τ)
        (Set.Ioo (0:ℝ) 1) :=
    homotopy_partial_tau_continuous_on_ioo hV hf hH hHV hH0 hH1 τ hτ
  have h_aes_Ioo :
      MeasureTheory.AEStronglyMeasurable
        (fun t => deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) τ)
        (MeasureTheory.volume.restrict (Set.Ioo (0:ℝ) 1)) :=
    h_cont.aestronglyMeasurable measurableSet_Ioo
  have hset_eq : Set.uIoc (0:ℝ) 1 = Set.Ioc (0:ℝ) 1 := Set.uIoc_of_le zero_le_one
  rw [hset_eq, ← MeasureTheory.Measure.restrict_congr_set MeasureTheory.Ioo_ae_eq_Ioc]
  exact h_aes_Ioo

end Problems.residue_thm
