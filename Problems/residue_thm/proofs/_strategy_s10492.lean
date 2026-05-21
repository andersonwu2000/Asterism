import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_int_telescope_partition
import Problems.residue_thm.proofs.L_piecewise_path_int_eq_on_ball

namespace Problems.residue_thm

-- Concordance via piecewise FTC on each ball of the cover.
-- (1) `piecewise_path_int_eq_on_ball` (per index i < n): the integrals of
--     `g(γ) γ'` and `g(η) η'` over [t i, t (i+1)] agree, because both curves
--     lie in the ball B_i ⊆ U on which `g` admits a primitive and they share
--     endpoint values η (t i) = γ (t i).
-- (2) `path_int_telescope_partition`: summing the per-piece equalities via
--     `intervalIntegral.sum_integral_adjacent_intervals` rebuilds the full
--     integrals over [0,1] and yields the concordance equality.
theorem s10492
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∀ (η : ℝ → ℂ) (n : ℕ) (t : ℕ → ℝ) (centers : ℕ → ℂ) (radii : ℕ → ℝ),
      ContDiffOn ℝ 1 η (Set.Icc (0:ℝ) 1) →
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U →
      t 0 = 0 → t n = 1 →
      (∀ i, i < n → t i ≤ t (i+1)) →
      (∀ i, i < n → 0 < radii i) →
      (∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U) →
      (∀ i, i < n → Set.MapsTo γ (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) →
      (∀ i, i < n → Set.MapsTo η (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) →
      (∀ i, i ≤ n → η (t i) = γ (t i)) →
      (∫ t in (0:ℝ)..1, g (η t) * deriv η t)
        = (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t)  := by
  intro η n t centers radii hη_C1 hηU ht0 htn ht_mono hr_pos hball_sub hγ_in hη_in h_agree
  have h_piece : ∀ i, i < n →
      (∫ s in t i..t (i+1), g (γ s) * deriv γ s) =
      (∫ s in t i..t (i+1), g (η s) * deriv η s) := fun i hi =>
    piecewise_path_int_eq_on_ball hg hγ hη_C1 ht0 htn ht_mono hball_sub hγ_in hη_in h_agree i hi
  exact path_int_telescope_partition hU hg hγ hmaps hη_C1 hηU ht0 htn ht_mono h_piece

end Problems.residue_thm
