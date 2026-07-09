import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Complex.HasPrimitives

/-!
# Fundamental theorem of calculus for path integrals

This file establishes the **fundamental theorem of calculus** (FTC) for path integrals of
holomorphic functions along $C^1$ paths.

Given a holomorphic function $f : \mathbb{C} \to \mathbb{C}$ admitting a primitive $F$ on an
open set $U$, and a $C^1$ path $\gamma : [0, 1] \to U$, the path integral satisfies
$$\int_0^1 f(\gamma(t)) \cdot \gamma'(t) \, dt = F(\gamma(1)) - F(\gamma(0)).$$

## Main statements

- `chain_rule_interior`: $F \circ \gamma$ has derivative $f(\gamma(t)) \cdot \gamma'(t)$
  at each interior point of $[0, 1]$.
- `continuous_on_f_circ_gamma`: $F \circ \gamma$ is continuous on $[0, 1]$.

- `interval_integrable_integrand`: $t \mapsto f(\gamma(t)) \cdot \gamma'(t)$ is interval-integrable.
- `path_integral_eq_primitive_diff`: the FTC equality for a fixed primitive $F$ on $U$.
- `integral_eq_sub_of_differentiableOn_ball`: the FTC equality when $f$ is differentiable on a
  ball, using `DifferentiableOn.isExactOn_ball` to produce a primitive.

## Implementation notes

The main proof assembles three ingredients via
`intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le`: continuity of $F \circ \gamma$ on the
closed interval, the chain-rule derivative at interior points, and integrability of the integrand.
-/

namespace Library.Analysis.ResidueTheorem.PathIntegralFTC

/-- The composition $F \circ \gamma$ has derivative $f(\gamma(t)) \cdot \gamma'(t)$ at each
interior point $t \in (0, 1)$, given that $F$ is a primitive of $f$ on the open set $U$ and
$\gamma : [0, 1] \to U$ is $C^1$. The proof uses `ContDiffOn.differentiableOn` to obtain
`DifferentiableAt ℝ γ t`, then applies `HasDerivAt.comp`. -/
theorem chain_rule_interior
    {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (hF : ∀ z ∈ U, HasDerivAt F (f z) z)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U) :
    ∀ t ∈ Set.Ioo (0 : ℝ) 1,
      HasDerivAt (fun s => F (γ s)) (f (γ t) * deriv γ t) t := by
  intro t ht
  have htIcc : t ∈ Set.Icc (0 : ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hγU_t : γ t ∈ U := hγU htIcc
  have hF_t : HasDerivAt F (f (γ t)) (γ t) := hF (γ t) hγU_t
  have hIcc_nhds : Set.Icc (0 : ℝ) 1 ∈ nhds t := Icc_mem_nhds ht.1 ht.2
  have hDiff : DifferentiableAt ℝ γ t :=
    (hγC1.differentiableOn (by norm_num)).differentiableAt hIcc_nhds
  exact hF_t.comp t hDiff.hasDerivAt

/-- $F \circ \gamma$ is continuous on $[0, 1]$, given that $F$ is a primitive of $f$ on the
open set $U$ and $\gamma : [0, 1] \to U$ is $C^1$. -/
theorem continuous_on_f_circ_gamma
    {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (hF : ∀ z ∈ U, HasDerivAt F (f z) z)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U) :
    ContinuousOn (fun t => F (γ t)) (Set.Icc (0 : ℝ) 1) := by
  have hFcont : ContinuousOn F U := fun z hz => (hF z hz).continuousAt.continuousWithinAt
  have hγcont : ContinuousOn γ (Set.Icc 0 1) := hγC1.continuousOn
  exact hFcont.comp hγcont hγU

/-- The integrand $t \mapsto f(\gamma(t)) \cdot \gamma'(t)$ is interval-integrable on $[0, 1]$,
given that $F$ is a primitive of $f$ on the open set $U$ and $\gamma : [0, 1] \to U$ is $C^1$.
The key step replaces `deriv γ t` with `derivWithin γ (Set.Icc 0 1) t` almost everywhere, since
both agree away from the boundary. -/
theorem interval_integrable_integrand
    {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ∀ z ∈ U, HasDerivAt F (f z) z)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U) :
    IntervalIntegrable (fun t => f (γ t) * deriv γ t) MeasureTheory.volume 0 1 := by
  have hFdiff : DifferentiableOn ℂ F U :=
    fun z hz => (hF z hz).differentiableAt.differentiableWithinAt
  have hfcont : ContinuousOn f U := by
    have hderivF : DifferentiableOn ℂ (deriv F) U := hFdiff.deriv hU
    exact hderivF.continuousOn.congr (fun z hz => ((hF z hz).deriv).symm)
  have hfγcont : ContinuousOn (fun t => f (γ t)) (Set.Icc 0 1) :=
    hfcont.comp hγC1.continuousOn hγU
  have hdwcont : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγC1.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hprod : ContinuousOn (fun t => f (γ t) * derivWithin γ (Set.Icc 0 1) t) (Set.Icc 0 1) :=
    hfγcont.mul hdwcont
  have hint : IntervalIntegrable (fun t => f (γ t) * derivWithin γ (Set.Icc 0 1) t)
      MeasureTheory.volume 0 1 := hprod.intervalIntegrable_of_Icc (by norm_num : (0 : ℝ) ≤ 1)
  apply hint.congr_ae
  apply (MeasureTheory.ae_restrict_iff' measurableSet_uIoc).mpr
  have hae_ne : ∀ᵐ t ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ), t ≠ (1 : ℝ) :=
    MeasureTheory.measure_eq_zero_iff_ae_notMem.mp Real.volume_singleton
  filter_upwards [hae_ne] with t ht_ne ht_mem
  congr 1
  have htIoo : t ∈ Set.Ioo (0 : ℝ) 1 := by
    have hmem : t ∈ Set.Ioc (0 : ℝ) 1 := by
      rwa [← Set.uIoc_of_le (by norm_num : (0 : ℝ) ≤ 1)]
    exact ⟨hmem.1, lt_of_le_of_ne hmem.2 ht_ne⟩
  exact derivWithin_of_mem_nhds (Icc_mem_nhds htIoo.1 htIoo.2)

/-- **Fundamental theorem of calculus for path integrals**: if $F$ is a primitive of $f$ on an
open set $U \subseteq \mathbb{C}$ and $\gamma : [0, 1] \to U$ is a $C^1$ path, then
$$\int_0^1 f(\gamma(t)) \cdot \gamma'(t) \, dt = F(\gamma(1)) - F(\gamma(0)).$$ -/
theorem path_integral_eq_primitive_diff
    {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ∀ z ∈ U, HasDerivAt F (f z) z)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U) :
    (∫ t in (0 : ℝ)..1, f (γ t) * deriv γ t) = F (γ 1) - F (γ 0) := by
  have h_cont := continuous_on_f_circ_gamma hU hF hγC1 hγU
  have h_chain := chain_rule_interior hU hF hγC1 hγU
  have h_int := interval_integrable_integrand hU hF hγC1 hγU
  exact intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le zero_le_one h_cont h_chain h_int

/-- Given a function $f$ holomorphic on `Metric.ball z₀ R` and a $C^1$ path
$\gamma : [a, b] \to$ `Metric.ball z₀ R`, there exists a primitive $F$ of $f$ on the ball such
that $\int_a^b f(\gamma(t)) \cdot \gamma'(t) \, dt = F(\gamma(b)) - F(\gamma(a))$.
The primitive is produced by `DifferentiableOn.isExactOn_ball`. -/
theorem integral_eq_sub_of_differentiableOn_ball
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ' : ℝ → ℂ} {a b : ℝ}
    (hab : a ≤ b)
    (hf : DifferentiableOn ℂ f (Metric.ball z₀ R))
    (hγ : ContDiffOn ℝ 1 γ' (Set.Icc a b))
    (hγU : Set.MapsTo γ' (Set.Icc a b) (Metric.ball z₀ R)) :
    ∃ F : ℂ → ℂ,
      (∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z) ∧
      (∫ t in a..b, f (γ' t) * deriv γ' t) = F (γ' b) - F (γ' a) := by
  obtain ⟨F, hF⟩ := hf.isExactOn_ball
  refine ⟨F, hF, ?_⟩
  have h_cont : ContinuousOn (fun t => F (γ' t)) (Set.Icc a b) := by
    have hFcont : ContinuousOn F (Metric.ball z₀ R) :=
      fun z hz => (hF z hz).continuousAt.continuousWithinAt
    exact hFcont.comp hγ.continuousOn hγU
  have h_deriv : ∀ x ∈ Set.Ioo a b,
      HasDerivAt (fun s => F (γ' s)) (f (γ' x) * deriv γ' x) x := by
    intro x hx
    have hx_mem : x ∈ Set.Icc a b := Set.mem_Icc_of_Ioo hx
    have hFγx : HasDerivAt F (f (γ' x)) (γ' x) := hF (γ' x) (hγU hx_mem)
    have hIcc_nhds : Set.Icc a b ∈ nhds x := Icc_mem_nhds hx.1 hx.2
    have hγDA : DifferentiableAt ℝ γ' x :=
      (hγ.differentiableOn one_ne_zero x hx_mem).differentiableAt hIcc_nhds
    exact hFγx.comp x hγDA.hasDerivAt
  have h_int : IntervalIntegrable (fun t => f (γ' t) * deriv γ' t)
      MeasureTheory.volume a b := by
    rcases eq_or_lt_of_le hab with rfl | hab_lt
    · constructor <;> simp [MeasureTheory.integrableOn_empty]
    · have hfcont : ContinuousOn f (Metric.ball z₀ R) := hf.continuousOn
      have huniq : UniqueDiffOn ℝ (Set.Icc a b) := uniqueDiffOn_Icc hab_lt
      have hcont : ContinuousOn (fun t => f (γ' t) * derivWithin γ' (Set.Icc a b) t)
          (Set.Icc a b) :=
        (hfcont.comp hγ.continuousOn hγU).mul (hγ.continuousOn_derivWithin huniq le_rfl)
      apply (hcont.intervalIntegrable_of_Icc hab).congr_ae
      rw [Set.uIoc_of_le hab]
      refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict
        MeasureTheory.Ioo_ae_eq_Ioc ?_
      filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
      simp [derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 ht.2)]
  exact intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le hab h_cont h_deriv h_int

end Library.Analysis.ResidueTheorem.PathIntegralFTC
