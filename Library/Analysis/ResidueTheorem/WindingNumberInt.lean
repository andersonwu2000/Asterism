import Mathlib.RingTheory.SimpleRing.Principal
import Library.Analysis.ResidueTheorem.WindingNumberDiff

/-!
# Winding number integrality

This file proves that for a C¹ closed path `γ : ℝ → ℂ` whose image avoids a point `a : ℂ`,
the path integral `∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a)` is an integer multiple of
`2 * Real.pi * Complex.I`.

The key steps are:
1. The fundamental theorem of calculus gives a `HasDerivWithinAt` statement for the integral.
2. The chain and product rules show the `derivWithin` of
   `fun s => Complex.exp (-(∫ t in (0 : ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a)`
   is zero on `[0, 1)`.
3. A constancy lemma converts this to `exp(G(s)) * (γ 0 - a) = γ s - a` for all `s ∈ [0, 1]`.
4. Evaluating at `s = 1` and using `γ 0 = γ 1` gives `exp(G(1)) = 1`, hence integrality.

## Main definitions

- `Complex.windingNumber`: the winding number of a path `γ` around a point `a`, defined as
  the integer `k` such that the path integral equals `2 * Real.pi * Complex.I * k`, or `0`
  when no such integer exists.

## Main statements

- `exists_winding_integer`: for a C¹ closed path `γ` on `[0, 1]` whose image avoids `a`,
  `∃ k : ℤ, ∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a) = 2 * Real.pi * Complex.I * k`.
-/

open Library.Analysis.ResidueTheorem.WindingNumberDiff

namespace Complex

open Classical in
/--
Winding number of a C¹ closed path `γ : ℝ → ℂ` around a point `a ∈ ℂ`.

Defined classically: if there exists an integer `k : ℤ` such that
`∫ t in 0..1, deriv γ t / (γ t - a) = 2πi · k`, return that `k`;
otherwise return `0`.

For C¹ closed paths whose image avoids `a`, such a `k` always exists
(integrality theorem). Outside that hypothesis class the default `0` makes
the function total without committing to a value.
-/
noncomputable def windingNumber (γ : ℝ → ℂ) (a : ℂ) : ℤ :=
  if h : ∃ k : ℤ,
        (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k
    then Classical.choose h
    else 0

end Complex

namespace Library.Analysis.ResidueTheorem.WindingNumberInt

/-- Pointwise algebraic identity expressing that the derivative of
`fun s => Complex.exp (-(∫ t in (0 : ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a)`
is zero: the two terms in the product rule cancel via `γ s ≠ a`. -/
theorem chain_deriv_sum_eq_zero
    {γ : ℝ → ℂ} {a : ℂ}
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      -(deriv γ s / (γ s - a)) *
        Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a) +
      Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * deriv γ s = 0 := by grind

/-- The path-minus-constant function `fun s => γ s - a` has `HasDerivWithinAt` with value
`derivWithin γ (Set.Icc 0 1) s` on `[0, 1]`. -/
theorem has_deriv_within_at_path_sub_const
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hclosed : γ 0 = γ 1)
    (_havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0 : ℝ) 1,
      HasDerivWithinAt (fun s => γ s - a)
        (derivWithin γ (Set.Icc (0 : ℝ) 1) s) (Set.Icc (0 : ℝ) 1) s := by
  intro s hs
  have hdiff := hγ.differentiableOn (by norm_num) s (Set.Ico_subset_Icc_self hs)
  exact hdiff.hasDerivWithinAt.sub_const a

/-- The product-rule output for `exp(-G(s)) * (γ s - a)` expressed in terms of `derivWithin`
equals the same expression in terms of `deriv`. Both sides equal `0` when `γ s ≠ a`. -/
theorem exp_neg_integral_mul_derivWithin_eq_deriv
    {γ : ℝ → ℂ} {a : ℂ}
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      -(derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a)) *
          Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a) +
        Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) *
          derivWithin γ (Set.Icc (0:ℝ) 1) s =
      -(deriv γ s / (γ s - a)) *
          Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a) +
        Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * deriv γ s := by grind

/-- Fundamental theorem of calculus for `∫₀ˢ derivWithin γ (Icc 0 1) t / (γ t - a)`:
the integral has `HasDerivWithinAt` with value `derivWithin γ (Icc 0 1) s / (γ s - a)` on
`[0, 1]`. The continuity of the integrand (`continuousOn_integrand`) drives both
integrability and the pointwise FTC derivative value. -/
theorem has_deriv_within_at_integral_derivWithin_div
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => ∫ t in (0:ℝ)..s, derivWithin γ (Set.Icc (0:ℝ) 1) t / (γ t - a))
        (derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a))
        (Set.Icc (0:ℝ) 1) s := by
  have hcont := continuousOn_integrand hγ hclosed havoid
  intro s hs
  have hsicc : s ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hs
  haveI : Fact (s ∈ Set.Icc (0:ℝ) 1) := ⟨hsicc⟩
  have hsub : Set.uIcc (0:ℝ) s ⊆ Set.Icc 0 1 := by
    rw [Set.uIcc_of_le hs.1]; exact Set.Icc_subset_Icc_right hsicc.2
  exact intervalIntegral.integral_hasDerivWithinAt_right
    ((hcont.mono hsub).intervalIntegrable)
    ⟨Set.Icc 0 1, self_mem_nhdsWithin, hcont.aestronglyMeasurable measurableSet_Icc⟩
    (hcont s hsicc)

/-- Fundamental theorem of calculus for `∫₀ˢ deriv γ t / (γ t - a)` with derivative value
`derivWithin γ (Icc 0 1) s / (γ s - a)`. Direct FTC fails because `deriv γ` may be junk
at the endpoints; instead, the proof swaps to the `derivWithin`-integrand (which is
continuous on `Icc 0 1`) via `integral_eq_integral_deriv_within`, applies FTC there, and
transfers via `HasDerivWithinAt.congr`. -/
theorem has_deriv_within_at_integral_deriv_div
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
        (derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a))
        (Set.Icc (0:ℝ) 1) s := by
  intro s hs
  have hs_icc : s ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hs
  have h_ftc := has_deriv_within_at_integral_derivWithin_div hγ hclosed havoid s hs
  have h_eq := integral_eq_integral_deriv_within hγ hclosed havoid
  exact h_ftc.congr (fun y hy => h_eq y hy) (h_eq s hs_icc)

/-- Chain rule: `fun s => Complex.exp (-(∫ t in (0 : ℝ)..s, deriv γ t / (γ t - a)))` has
`HasDerivWithinAt` with value
`-(derivWithin γ (Icc 0 1) s / (γ s - a)) * exp(-G(s))` on `[0, 1]`. -/
theorem has_deriv_within_at_exp_neg_integral
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
        (-(derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a)) *
           Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
        (Set.Icc (0:ℝ) 1) s := by
  intro s hs
  have h_int : HasDerivWithinAt
      (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
      (derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a))
      (Set.Icc (0:ℝ) 1) s := has_deriv_within_at_integral_deriv_div hγ hclosed havoid s hs
  have h_neg : HasDerivWithinAt
      (fun s => -(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)))
      (-(derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a)))
      (Set.Icc (0:ℝ) 1) s := h_int.neg
  have h_exp : HasDerivWithinAt
      (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
      (Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) *
         -(derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a)))
      (Set.Icc (0:ℝ) 1) s := h_neg.cexp
  rw [mul_comm]
  exact h_exp

/-- Product rule: `fun s => exp(-G(s)) * (γ s - a)` has `HasDerivWithinAt` with value equal
to the sum of the two product-rule terms on `[0, 1)`. The intermediate derivative values use
`derivWithin γ (Icc 0 1) s` rather than `deriv γ s` to avoid junk values at the endpoints
where `ContDiffOn ℝ 1 γ (Icc 0 1)` does not imply `DifferentiableAt`. -/
theorem has_deriv_within_at_exp_neg_integral_mul
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a))
        (-(deriv γ s / (γ s - a)) *
           Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a) +
         Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * deriv γ s)
        (Set.Icc (0:ℝ) 1) s := by
  intro s hs
  have h_exp := has_deriv_within_at_exp_neg_integral hγ hclosed havoid s hs
  have h_gamma := has_deriv_within_at_path_sub_const hγ hclosed havoid s hs
  have h_value_eq := exp_neg_integral_mul_derivWithin_eq_deriv hγ hclosed havoid s hs
  have h_combined := h_exp.mul h_gamma
  rw [h_value_eq] at h_combined
  exact h_combined

/-- The `derivWithin` of `fun s => exp(-G(s)) * (γ s - a)` is zero on `[0, 1)`.
Follows from `has_deriv_within_at_exp_neg_integral_mul` and `chain_deriv_sum_eq_zero`,
closing via `HasDerivWithinAt.derivWithin` and `uniqueDiffOn_Icc_zero_one`. -/
theorem deriv_exp_neg_path_zero
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      derivWithin
        (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a))
        (Set.Icc (0:ℝ) 1) s = 0 := by
  intro s hs
  have h_chain := has_deriv_within_at_exp_neg_integral_mul hγ hclosed havoid s hs
  have h_zero := chain_deriv_sum_eq_zero hγ hclosed havoid s hs
  rw [h_zero] at h_chain
  exact h_chain.derivWithin (uniqueDiffOn_Icc_zero_one s (Set.Ico_subset_Icc_self hs))

/-- Constancy lemma: `Complex.exp (∫₀ˢ deriv γ t / (γ t - a)) * (γ 0 - a) = γ s - a`
for all `s ∈ [0, 1]`.

Proved by showing the auxiliary function `H s = exp(-G(s)) * (γ s - a)` is differentiable
on `[0, 1]` with `derivWithin H = 0` on `[0, 1)`, hence constant by
`constant_of_derivWithin_zero`. Evaluating at `s = 0` gives `H 0 = γ 0 - a`, and
multiplying both sides by `exp(G(s))` and simplifying via `Complex.exp_add` yields the
result. -/
theorem exp_path_integral_mul_eq
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Icc (0:ℝ) 1,
      Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) * (γ 0 - a) = γ s - a := by
  set H : ℝ → ℂ := fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) *
                              (γ s - a) with hH_def
  have h_diff : DifferentiableOn ℝ H (Set.Icc (0:ℝ) 1) :=
    differentiableOn_exp_neg_path hγ hclosed havoid
  have h_deriv_zero : ∀ s ∈ Set.Ico (0:ℝ) 1, derivWithin H (Set.Icc (0:ℝ) 1) s = 0 :=
    deriv_exp_neg_path_zero hγ hclosed havoid
  have h_constant : ∀ s ∈ Set.Icc (0:ℝ) 1, H s = H 0 :=
    constant_of_derivWithin_zero h_diff h_deriv_zero
  have h_H0 : H 0 = γ 0 - a := by
    simp [hH_def, intervalIntegral.integral_same]
  intro s hs
  have h_inv : Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a) =
               γ 0 - a := by
    have := (h_constant s hs).trans h_H0
    simpa [hH_def] using this
  have hexp_cancel : Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) *
                     Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) = 1 := by
    rw [← Complex.exp_add]
    simp
  calc Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) * (γ 0 - a)
      = Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) *
          (Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a)) := by
        rw [h_inv]
    _ = (Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) *
          Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)))) * (γ s - a) := by ring
    _ = 1 * (γ s - a) := by rw [hexp_cancel]
    _ = γ s - a := by ring

/-- For a C¹ closed path `γ` on `[0, 1]` avoiding `a`, the total path integral satisfies
`Complex.exp (∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a)) = 1`. -/
theorem exp_path_integral_eq_one
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    Complex.exp (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 1 := by
  have h_const := exp_path_integral_mul_eq hγ hclosed havoid
  have h1 := h_const 1 ⟨zero_le_one, le_refl 1⟩
  rw [← hclosed] at h1
  have hne : γ 0 - a ≠ 0 :=
    sub_ne_zero.mpr (havoid 0 ⟨le_refl 0, zero_le_one⟩)
  exact (mul_left_eq_self₀.mp h1).resolve_right hne

/-- **Winding number integrality**: for a C¹ closed path `γ` on `[0, 1]` whose image avoids
`a : ℂ`, there exists `k : ℤ` such that
`∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a) = 2 * Real.pi * Complex.I * k`. -/
theorem exists_winding_integer
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∃ k : ℤ, (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a))
          = 2 * Real.pi * Complex.I * k := by
  have h_exp := exp_path_integral_eq_one hγ hclosed havoid
  obtain ⟨n, hn⟩ := Complex.exp_eq_one_iff.mp h_exp
  exact ⟨n, by rw [hn]; ring⟩

end Library.Analysis.ResidueTheorem.WindingNumberInt
