import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- path_integral_split_subintervals: splits ∫₀¹ g(γ)·γ' into a sum over N
-- adjacent subintervals [j/N,(j+1)/N] via sum_integral_adjacent_intervals;
-- IntervalIntegrable via derivWithin continuity + DifferentiableAt.derivWithin on the interior.
-- entry_kind: Builder
theorem path_integral_split_subintervals
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (N : ℕ) (hNpos : 0 < N) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) =
      ∑ j ∈ Finset.range N,
        (∫ t in ((j:ℝ)/N)..(((j:ℝ)+1)/N), g (γ t) * deriv γ t) := by
  have hNpos' : (0 : ℝ) < N := Nat.cast_pos.mpr hNpos
  have hN_ne : (N : ℝ) ≠ 0 := hNpos'.ne'
  -- ContinuousOn of derivWithin γ (Icc 0 1) on Icc 0 1
  have hcont_dv : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  -- ContinuousOn of g ∘ γ on Icc 0 1
  have hcont_g : ContinuousOn (fun t : ℝ => g (γ t)) (Set.Icc 0 1) :=
    hg.continuousOn.comp hγ.continuousOn (fun t ht => hmaps ht)
  -- IntervalIntegrable on each sub-interval [k/N, (k+1)/N]
  have hint' : ∀ k < N, IntervalIntegrable (fun t => g (γ t) * deriv γ t)
      MeasureTheory.volume ((k : ℝ) / N) ((↑(k + 1) : ℝ) / N) := by
    intro k hk
    push_cast
    -- Goal now: IntervalIntegrable ... (↑k / ↑N) ((↑k + 1) / ↑N)
    have hk1N : (k : ℝ) + 1 ≤ N := by exact_mod_cast Nat.succ_le_of_lt hk
    have hkN : (k : ℝ) / N ≤ ((k : ℝ) + 1) / N :=
      div_le_div_of_nonneg_right (by linarith) hNpos'.le
    have hsubset : Set.Icc ((k : ℝ) / N) (((k : ℝ) + 1) / N) ⊆ Set.Icc 0 1 := fun t ⟨ht1, ht2⟩ =>
      ⟨le_trans (by positivity) ht1, le_trans ht2 ((div_le_one hNpos').mpr hk1N)⟩
    apply ((hcont_g.mono hsubset).mul (hcont_dv.mono hsubset)
      |>.intervalIntegrable_of_Icc hkN) |>.congr_ae
    simp only [hkN, Set.uIoc_of_le]
    rw [← MeasureTheory.restrict_Ioo_eq_restrict_Ioc]
    filter_upwards [MeasureTheory.self_mem_ae_restrict measurableSet_Ioo] with t ht
    simp only [Pi.mul_apply]
    have hmem : Set.Icc 0 1 ∈ nhds t :=
      Icc_mem_nhds (lt_of_le_of_lt (by positivity) ht.1)
                   (lt_of_lt_of_le ht.2 ((div_le_one hNpos').mpr hk1N))
    have hda : DifferentiableAt ℝ γ t :=
      (hγ.differentiableOn one_ne_zero t
        (hsubset (Set.Ioo_subset_Icc_self ht))).differentiableAt hmem
    rw [hda.derivWithin (uniqueDiffOn_Icc_zero_one t (hsubset (Set.Ioo_subset_Icc_self ht)))]
  -- Apply sum_integral_adjacent_intervals
  have key := (intervalIntegral.sum_integral_adjacent_intervals
    (a := fun k => (k : ℝ) / N) (f := fun t => g (γ t) * deriv γ t) hint').symm
  simp only [Nat.cast_zero, zero_div, div_self hN_ne] at key
  simp_rw [show ∀ j : ℕ, ((j : ℝ) + 1) / N = (↑(j + 1) : ℝ) / N from fun j => by push_cast; ring]
  exact key

end Problems.residue_thm