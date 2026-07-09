import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.MeasureTheory.Integral.IntervalIntegral.FundThmCalculus

/-!
# Differentiability lemmas for the winding number integral

This file provides differentiability results needed to show that the winding number
of a closed $C^1$ path $\gamma : [0,1] \to \mathbb{C}$ around a point $a$ is an integer.

The key object is the function
$s \mapsto \exp(-\int_0^s \gamma'(t)/(\gamma(t)-a)\,dt) \cdot (\gamma(s) - a)$,
whose constancy (proved elsewhere) implies the winding number is an integer.

## Main statements

- `differentiableOn_integral_path`: the antiderivative
  $s \mapsto \int_0^s \gamma'(t)/(\gamma(t)-a)\,dt$ is differentiable on $[0,1]$.
- `differentiableOn_exp_neg_path`: the function
  $s \mapsto \exp(-\int_0^s \gamma'(t)/(\gamma(t)-a)\,dt) \cdot (\gamma(s) - a)$
  is differentiable on $[0,1]$.

## Implementation notes

To apply the fundamental theorem of calculus, we replace `deriv γ` by
`derivWithin γ (Set.Icc 0 1)` inside the integrand. The two agree a.e. on $(0, 1)$,
but `derivWithin` is continuous on the closed interval via
`ContDiffOn.continuousOn_derivWithin`, as required by FTC.
-/

namespace Library.Analysis.ResidueTheorem.WindingNumberDiff

/-- The path `γ` shifted by a constant `a` is differentiable on $[0,1]$
when `γ` is $C^1$ on that interval. -/
theorem differentiableOn_gamma_sub_a
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1)) :
    DifferentiableOn ℝ
      (fun s => γ s - a)
      (Set.Icc (0:ℝ) 1) := by fun_prop

/-- The interval integrals of `deriv γ t / (γ t - a)` and
`derivWithin γ (Set.Icc 0 1) t / (γ t - a)` agree on $[0,s]$ for every $s \in [0,1]$.

The two integrands differ only at the single point $s$, which has measure zero,
so `intervalIntegral.integral_congr_ae` applies. -/
theorem integral_eq_integral_deriv_within
    {γ : ℝ → ℂ} {a : ℂ}
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hclosed : γ 0 = γ 1)
    (_havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Icc (0:ℝ) 1,
      (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) =
        (∫ t in (0:ℝ)..s, derivWithin γ (Set.Icc (0:ℝ) 1) t / (γ t - a)) := by
  intro s hs
  have hs0 : (0:ℝ) ≤ s := hs.1
  have hs1 : s ≤ 1 := hs.2
  apply intervalIntegral.integral_congr_ae
  have hne : ∀ᵐ (x : ℝ), x ≠ s := by
    rw [MeasureTheory.ae_iff]; simp
  filter_upwards [hne] with t hts ht
  simp only [Set.uIoc_of_le hs0, Set.mem_Ioc] at ht
  congr 1
  symm
  apply derivWithin_of_mem_nhds
  exact Icc_mem_nhds ht.1 (lt_of_lt_of_le (lt_of_le_of_ne ht.2 hts) hs1)

/-- The integrand `t ↦ derivWithin γ (Set.Icc 0 1) t / (γ t - a)` is continuous on $[0,1]$
when `γ` is $C^1$ and avoids `a`. -/
theorem continuousOn_integrand
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ContinuousOn
      (fun t => derivWithin γ (Set.Icc (0 : ℝ) 1) t / (γ t - a))
      (Set.Icc (0 : ℝ) 1) := by
  have h1 : ContinuousOn (derivWithin γ (Set.Icc (0 : ℝ) 1)) (Set.Icc (0 : ℝ) 1) :=
    hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have h2 : ContinuousOn (fun t => γ t - a) (Set.Icc (0 : ℝ) 1) :=
    hγ.continuousOn.sub continuousOn_const
  have h3 : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t - a ≠ 0 :=
    fun t ht => sub_ne_zero.mpr (havoid t ht)
  exact h1.div h2 h3

/-- For any continuous function `f` on $[0,1]$, the antiderivative
`s ↦ ∫ t in (0 : ℝ)..s, f t` is `DifferentiableOn ℝ` on $[0,1]$,
by the fundamental theorem of calculus
(`intervalIntegral.integral_hasDerivWithinAt_right`). -/
theorem differentiableOn_integral_of_continuousOn
    {γ : ℝ → ℂ} {a : ℂ}
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hclosed : γ 0 = γ 1)
    (_havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (f : ℝ → ℂ)
    (hf : ContinuousOn f (Set.Icc (0 : ℝ) 1)) :
    DifferentiableOn ℝ (fun s => ∫ t in (0 : ℝ)..s, f t) (Set.Icc (0 : ℝ) 1) := by
  intro s hs
  haveI : Fact (s ∈ Set.Icc (0 : ℝ) 1) := ⟨hs⟩
  have hsub : Set.uIcc (0 : ℝ) s ⊆ Set.Icc 0 1 := by
    rw [Set.uIcc_of_le hs.1]; exact Set.Icc_subset_Icc_right hs.2
  apply (intervalIntegral.integral_hasDerivWithinAt_right
    ((hf.mono hsub).intervalIntegrable)
    ⟨Set.Icc 0 1, self_mem_nhdsWithin, hf.aestronglyMeasurable measurableSet_Icc⟩
    (hf s hs)).differentiableWithinAt

/-- The antiderivative `s ↦ ∫₀ˢ derivWithin γ (Set.Icc 0 1) t / (γ t - a) dt`
is `DifferentiableOn ℝ` on $[0,1]$.

Follows by combining `continuousOn_integrand` (the integrand is continuous on $[0,1]$)
with `differentiableOn_integral_of_continuousOn` (FTC). -/
theorem differentiableOn_integral_derivWithin
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    DifferentiableOn ℝ
      (fun s => ∫ t in (0:ℝ)..s, derivWithin γ (Set.Icc (0:ℝ) 1) t / (γ t - a))
      (Set.Icc (0:ℝ) 1) := by
  have h_cont := continuousOn_integrand hγ hclosed havoid
  exact differentiableOn_integral_of_continuousOn hγ hclosed havoid _ h_cont

/-- The antiderivative `s ↦ ∫₀ˢ deriv γ t / (γ t - a) dt`
is `DifferentiableOn ℝ` on $[0,1]$.

We replace `deriv γ` by `derivWithin γ (Set.Icc 0 1)` inside the integrand using
`integral_eq_integral_deriv_within` (they agree a.e.), then apply
`differentiableOn_integral_derivWithin` and transfer via `DifferentiableOn.congr`. -/
theorem differentiableOn_integral_path
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    DifferentiableOn ℝ
      (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
      (Set.Icc (0:ℝ) 1) := by
  have h_eq := integral_eq_integral_deriv_within hγ hclosed havoid
  have h_diff := differentiableOn_integral_derivWithin hγ hclosed havoid
  exact h_diff.congr h_eq

/-- The function `s ↦ exp(-∫₀ˢ deriv γ t / (γ t - a) dt)` is `DifferentiableOn ℝ`
on $[0,1]$.

Follows from `differentiableOn_integral_path` by composing with negation and
`Complex.exp` (which is entire). -/
theorem differentiableOn_exp_neg_integral
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    DifferentiableOn ℝ
      (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
      (Set.Icc (0:ℝ) 1) := by
  have h_int := differentiableOn_integral_path hγ hclosed havoid
  exact h_int.neg.cexp

/-- The function `s ↦ exp(-∫₀ˢ deriv γ t / (γ t - a) dt) * (γ s - a)`
is `DifferentiableOn ℝ` on $[0,1]$.

This is the key product whose constancy implies the winding number is an integer.
Differentiability follows from `differentiableOn_exp_neg_integral` and
`differentiableOn_gamma_sub_a` via `DifferentiableOn.mul`. -/
theorem differentiableOn_exp_neg_path
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    DifferentiableOn ℝ
      (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a))
      (Set.Icc (0:ℝ) 1) := by
  have h_exp := differentiableOn_exp_neg_integral hγ hclosed havoid
  have h_lin := differentiableOn_gamma_sub_a (a := a) hγ
  exact h_exp.mul h_lin

end Library.Analysis.ResidueTheorem.WindingNumberDiff
