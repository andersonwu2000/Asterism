import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- integral_linearity_finset_residue: splits an integral over a difference + pole sum
-- into the main integral minus a sum of residue-weighted pole integrals,
-- using interval integral linearity and Finset.sum/integral interchange.
theorem integral_linearity_finset_residue
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (h_main : IntervalIntegrable (fun t => f (γ t) * deriv γ t)
      MeasureTheory.volume 0 1)
    (h_pole : ∀ a ∈ T, IntervalIntegrable
      (fun t => Complex.residue f a / (γ t - a) * deriv γ t)
      MeasureTheory.volume 0 1) :
    (∫ t in (0 : ℝ)..1,
      (f (γ t) - ∑ a ∈ T, Complex.residue f a / (γ t - a)) * deriv γ t) =
      (∫ t in (0 : ℝ)..1, f (γ t) * deriv γ t) -
      ∑ a ∈ T, (∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a)) * Complex.residue f a := by
  have h_sum : IntervalIntegrable
      (fun t => ∑ a ∈ T, Complex.residue f a / (γ t - a) * deriv γ t)
      MeasureTheory.volume 0 1 := by
    have h := IntervalIntegrable.sum T (fun a ha => h_pole a ha)
    rw [show (∑ a ∈ T, fun t => Complex.residue f a / (γ t - a) * deriv γ t) =
        fun t => ∑ a ∈ T, Complex.residue f a / (γ t - a) * deriv γ t
        from funext (fun t => Finset.sum_apply t T _)] at h
    exact h
  simp_rw [sub_mul, Finset.sum_mul]
  rw [intervalIntegral.integral_sub h_main h_sum]
  congr 1
  rw [intervalIntegral.integral_finsetSum (fun a ha => h_pole a ha)]
  congr 1
  ext a
  rw [show (∫ t in (0 : ℝ)..1, Complex.residue f a / (γ t - a) * deriv γ t) =
      Complex.residue f a * ∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a) from by
    rw [show (fun t => Complex.residue f a / (γ t - a) * deriv γ t) =
        (fun t => Complex.residue f a * (deriv γ t / (γ t - a))) from by ext t; ring]
    exact intervalIntegral.integral_const_mul _ _]
  ring

end Problems.residue_thm
