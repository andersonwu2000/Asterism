import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- homotopy_integral_continuous_on_icc:
-- Replace deriv → derivWithin a.e. (bad point {1} has measure zero).
-- derivWithin (H τ) (Icc 0 1) t = fderivWithin(0,1) via HasFDerivWithinAt.comp_hasDerivWithinAt.
-- Joint continuity on Icc×Icc from ContDiffOn ℝ 2 via fderivWithin continuity.
-- Apply MeasureTheory.continuousOn_of_dominated on volume.restrict (Ioc 0 1).
theorem homotopy_integral_continuous_on_icc
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V) :
    ContinuousOn (fun τ => ∫ t in (0:ℝ)..1, f (H τ t) * deriv (H τ) t)
      (Set.Icc (0:ℝ) 1) := by
  -- (1) derivWithin (H τ) (Icc 0 1) t = fderivWithin(...)(τ,t)(0,1) by chain rule
  have hid : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      derivWithin (H τ) (Set.Icc 0 1) t =
      fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) (0, 1) := by
    intro τ hτ t ht
    have hcomp : HasFDerivWithinAt (fun q : ℝ × ℝ => H q.1 q.2)
        (fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
      (hH.differentiableOn (by norm_num) (τ, t) ⟨hτ, ht⟩).hasFDerivWithinAt
    have hg : HasDerivWithinAt (fun s => (τ, s)) ((0:ℝ), (1:ℝ)) (Set.Icc 0 1) t :=
      (hasDerivWithinAt_const t (Set.Icc 0 1) τ).prodMk (hasDerivWithinAt_id t (Set.Icc 0 1))
    have hmaps : Set.MapsTo (fun s => (τ, s)) (Set.Icc 0 1) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
      fun s hs => ⟨hτ, hs⟩
    have hchain := hcomp.comp_hasDerivWithinAt t hg hmaps
    have heq : (fun q : ℝ × ℝ => H q.1 q.2) ∘ (fun s => (τ, s)) = H τ := rfl
    rw [heq] at hchain
    exact hchain.derivWithin (uniqueDiffOn_Icc_zero_one t ht)
  -- (2) Joint continuity of (τ,t)↦f(H τ t)*derivWithin(H τ)(Icc 0 1) t on Icc×Icc
  have hfderiv_cont : ContinuousOn
      (fun p : ℝ × ℝ =>
        fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    hH.continuousOn_fderivWithin
      (uniqueDiffOn_Icc_zero_one.prod uniqueDiffOn_Icc_zero_one) (by norm_num)
  have hderiv_cont : ContinuousOn
      (fun p : ℝ × ℝ => derivWithin (H p.1) (Set.Icc 0 1) p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    (hfderiv_cont.clm_apply (continuousOn_const (c := ((0:ℝ), (1:ℝ))))).congr
      (fun p hp => hid p.1 hp.1 p.2 hp.2)
  have hintegrand_cont : ContinuousOn
      (fun p : ℝ × ℝ => f (H p.1 p.2) * derivWithin (H p.1) (Set.Icc 0 1) p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    (hf.continuousOn.comp hH.continuousOn (fun p hp => hHV p.1 hp.1 p.2 hp.2)).mul hderiv_cont
  -- (3) Compact bound
  obtain ⟨C, hC⟩ := (isCompact_Icc (a := (0:ℝ)) (b := 1)).prod isCompact_Icc
      |>.exists_bound_of_continuousOn hintegrand_cont
  -- (4) deriv → derivWithin swap a.e. (bad point {1} has volume 0)
  have hswap : ∀ τ ∈ Set.Icc (0:ℝ) 1,
      ∫ t in (0:ℝ)..1, f (H τ t) * deriv (H τ) t =
      ∫ t in (0:ℝ)..1, f (H τ t) * derivWithin (H τ) (Set.Icc 0 1) t := by
    intro τ hτ
    apply intervalIntegral.integral_congr_ae
    have hne : ∀ᵐ (x : ℝ), x ≠ 1 := by rw [MeasureTheory.ae_iff]; simp
    filter_upwards [hne] with t ht1 ht
    simp only [Set.uIoc_of_le zero_le_one, Set.mem_Ioc] at ht
    congr 1; symm
    exact derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 (lt_of_le_of_ne ht.2 ht1))
  -- (5) Conclude by dominated convergence on volume.restrict (Ioc 0 1)
  apply ContinuousOn.congr _ hswap
  simp_rw [intervalIntegral.integral_of_le zero_le_one]
  apply MeasureTheory.continuousOn_of_dominated (bound := fun _ => C)
  · -- AEStronglyMeasurable for each fixed τ
    intro τ hτ
    exact (hintegrand_cont.comp (continuousOn_const.prodMk continuousOn_id)
        (fun t ht => ⟨hτ, Set.Ioc_subset_Icc_self ht⟩)).aestronglyMeasurable measurableSet_Ioc
  · -- Pointwise bound ≤ C
    intro τ hτ
    filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioc] with t ht
    exact hC (τ, t) ⟨hτ, Set.Ioc_subset_Icc_self ht⟩
  · -- Constant bound is integrable (finite measure)
    exact MeasureTheory.integrableOn_const (hs := by
      rw [Real.volume_Ioc]; exact ENNReal.ofReal_ne_top)
  · -- A.e. ContinuousOn in τ
    filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioc] with t ht
    exact hintegrand_cont.comp (continuousOn_id.prodMk continuousOn_const)
        (fun τ hτ => ⟨hτ, Set.Ioc_subset_Icc_self ht⟩)

end Problems.residue_thm
