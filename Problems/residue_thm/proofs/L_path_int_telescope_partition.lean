import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- path_int_telescope_partition: telescope partition pieces using sum_integral_adjacent_intervals
theorem path_int_telescope_partition
    {U : Set ℂ} {g : ℂ → ℂ} {γ η : ℝ → ℂ} {n : ℕ} {t : ℕ → ℝ}
    (hU : IsOpen U) (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U)
    (hη : ContDiffOn ℝ 1 η (Set.Icc 0 1))
    (hηU : Set.MapsTo η (Set.Icc 0 1) U)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (ht_mono : ∀ i, i < n → t i ≤ t (i + 1))
    (hpiece : ∀ i, i < n →
      (∫ s in t i..t (i + 1), g (γ s) * deriv γ s) =
      (∫ s in t i..t (i + 1), g (η s) * deriv η s)) :
    (∫ s in (0:ℝ)..1, g (η s) * deriv η s) =
    (∫ s in (0:ℝ)..1, g (γ s) * deriv γ s) := by
  -- Monotonicity helpers
  have ht_start_le : ∀ k, k ≤ n → t 0 ≤ t k := by
    intro k
    induction k with
    | zero => intro; exact le_refl _
    | succ m ih =>
      intro hk
      exact (ih (Nat.le_of_succ_le hk)).trans (ht_mono m (Nat.lt_of_succ_le hk))
  have ht_le_end : ∀ k, k ≤ n → t k ≤ t n := by
    suffices h : ∀ k m, k ≤ m → m ≤ n → t k ≤ t m from fun k hk => h k n hk (le_refl n)
    intro k m hkm
    induction hkm with
    | refl => intro _; exact le_refl _
    | @step p hkp ih =>
      intro hpn
      exact (ih (Nat.le_of_succ_le hpn)).trans (ht_mono p (Nat.lt_of_succ_le hpn))
  -- Continuity of integrand using derivWithin (continuous on [0,1])
  have hγ_dw : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hη_dw : ContinuousOn (derivWithin η (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hη.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hγ_ic : ContinuousOn (fun s => g (γ s) * derivWithin γ (Set.Icc 0 1) s) (Set.Icc 0 1) :=
    (hg.continuousOn.comp hγ.continuousOn hγU).mul hγ_dw
  have hη_ic : ContinuousOn (fun s => g (η s) * derivWithin η (Set.Icc 0 1) s) (Set.Icc 0 1) :=
    (hg.continuousOn.comp hη.continuousOn hηU).mul hη_dw
  -- IntervalIntegrable for each piece (deriv agrees a.e. with derivWithin on sub-intervals)
  have hγ_int : ∀ k, k < n →
      IntervalIntegrable (fun s => g (γ s) * deriv γ s) MeasureTheory.volume (t k) (t (k + 1)) := by
    intro k hk
    have hk0 : (0 : ℝ) ≤ t k := ht0 ▸ ht_start_le k hk.le
    have hk1 : t (k + 1) ≤ (1 : ℝ) := htn ▸ ht_le_end (k + 1) hk
    have hmono := ht_mono k hk
    have hint_dw : IntervalIntegrable (fun s => g (γ s) * derivWithin γ (Set.Icc 0 1) s)
        MeasureTheory.volume (t k) (t (k + 1)) :=
      (hγ_ic.mono (Set.Icc_subset_Icc hk0 hk1)).intervalIntegrable_of_Icc hmono
    apply hint_dw.congr_ae
    rw [Set.uIoc_of_le hmono, ← MeasureTheory.restrict_Ioo_eq_restrict_Ioc]
    filter_upwards [MeasureTheory.self_mem_ae_restrict measurableSet_Ioo] with x ⟨hxk, hxk1⟩
    congr 1
    exact derivWithin_of_mem_nhds (Icc_mem_nhds (by linarith) (by linarith))
  have hη_int : ∀ k, k < n →
      IntervalIntegrable (fun s => g (η s) * deriv η s) MeasureTheory.volume (t k) (t (k + 1)) := by
    intro k hk
    have hk0 : (0 : ℝ) ≤ t k := ht0 ▸ ht_start_le k hk.le
    have hk1 : t (k + 1) ≤ (1 : ℝ) := htn ▸ ht_le_end (k + 1) hk
    have hmono := ht_mono k hk
    have hint_dw : IntervalIntegrable (fun s => g (η s) * derivWithin η (Set.Icc 0 1) s)
        MeasureTheory.volume (t k) (t (k + 1)) :=
      (hη_ic.mono (Set.Icc_subset_Icc hk0 hk1)).intervalIntegrable_of_Icc hmono
    apply hint_dw.congr_ae
    rw [Set.uIoc_of_le hmono, ← MeasureTheory.restrict_Ioo_eq_restrict_Ioc]
    filter_upwards [MeasureTheory.self_mem_ae_restrict measurableSet_Ioo] with x ⟨hxk, hxk1⟩
    congr 1
    exact derivWithin_of_mem_nhds (Icc_mem_nhds (by linarith) (by linarith))
  -- Telescope: sum of pieces equals whole integral
  have sum_γ := intervalIntegral.sum_integral_adjacent_intervals (a := t) hγ_int
  have sum_η := intervalIntegral.sum_integral_adjacent_intervals (a := t) hη_int
  rw [show (0 : ℝ) = t 0 from ht0.symm, show (1 : ℝ) = t n from htn.symm]
  rw [← sum_η, ← sum_γ]
  apply Finset.sum_congr rfl
  intro i hi
  exact (hpiece i (Finset.mem_range.mp hi)).symm

end Problems.residue_thm