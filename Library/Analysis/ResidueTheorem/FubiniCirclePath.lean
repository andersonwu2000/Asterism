import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.MeasureTheory.Integral.CircleIntegral
import Mathlib.MeasureTheory.Integral.Prod

/-!
# Fubini swap for circle path integrals

This file proves that for a meromorphic function `Q` analytic on `ℂ \ {a}` and a smooth
closed path `γ : ℝ → ℂ` avoiding `a`, the order of integration between the path integral
over `γ` and the circle integral `∮ w in C(a, ε)` can be exchanged.

## Main statements

- `q_kernel_aux_continuous_on_icc`: the Q-kernel integrand (using `derivWithin γ (Set.Icc 0 1)`)
  is continuous on `[0, 1] × [0, 2π]`.
- `q_kernel_deriv_eq_deriv_within_ae_prod`: `deriv γ` and `derivWithin γ (Set.Icc 0 1)` induce
  the same Q-kernel integrand a.e. on `(Ioc 0 1) × (Ioc 0 2π)`.
- `q_kernel_integrand_integrable`: the Q-kernel integrand is integrable on the product of
  restricted Lebesgue measures.
- `q_kernel_double_fubini_swap`: swaps the order of integration in the double interval integral.
- `fubini_swap_circle_path_q`: the path integral of `deriv γ t * ∮ Q w / (w - γ t)` equals the
  circle integral of `Q w * ∫ deriv γ t / (w - γ t)`.

## Implementation notes

The proof proceeds in three steps: (1) rewrite the circle integral `∮` as an interval integral
over `[0, 2π]`; (2) swap the order of the resulting double integral using joint integrability of
the rational kernel on the compact product `[0, 1] × [0, 2π]`; (3) refold the outer interval
integral back into a circle integral.

Integrability of the kernel is established via `derivWithin γ (Set.Icc 0 1)` (continuous on
`[0, 1]`) as a proxy for `deriv γ`, using an a.e. equality argument whose exceptional set
`{1} × [0, 2π]` has product measure zero.
-/

namespace Library.Analysis.ResidueTheorem.FubiniCirclePath

/-- The uncurried Q-kernel integrand
`(t, θ) ↦ derivWithin γ (Set.Icc 0 1) t * (deriv (circleMap a ε) θ •
  (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))`
is continuous on `[0, 1] × [0, 2π]`, given that `Q` is analytic on `ℂ \ {a}`, `γ` is `C¹`
on `[0, 1]`, and the circle of radius `ε` around `a` lies strictly inside the path `γ`. -/
theorem q_kernel_aux_continuous_on_icc
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (_hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (_hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (_hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) (_hε_R : ε < R)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    ContinuousOn
      (Function.uncurry (fun (t θ : ℝ) =>
        derivWithin γ (Set.Icc (0:ℝ) 1) t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi)) := by
  -- circleMap a ε θ is never equal to a (it lives on the sphere of radius ε > 0)
  have hcm_ne_a : ∀ θ : ℝ, circleMap a ε θ ≠ a := by
    intro θ h
    have hmem := circleMap_mem_sphere a hε_pos.le θ
    simp only [Metric.mem_sphere, h, dist_self] at hmem
    linarith
  -- circleMap a ε θ ≠ γ t for t ∈ Icc 0 1 (γ t is outside the circle)
  have hne : ∀ p : ℝ × ℝ, p ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi) →
      circleMap a ε p.2 - γ p.1 ≠ 0 := by
    intro p hp h
    rw [sub_eq_zero] at h
    have hmem := circleMap_mem_sphere a hε_pos.le p.2
    rw [Metric.mem_sphere, h] at hmem
    linarith [hε_sep p.1 hp.1]
  -- Q ∘ circleMap a ε is continuous (Q analytic off {a}, circleMap avoids a)
  have hQ_cts : Continuous (fun θ => Q (circleMap a ε θ)) :=
    hQ_an.continuousOn.comp_continuous (continuous_circleMap a ε)
      (fun θ => Set.mem_diff_of_mem (Set.mem_univ _)
        (fun h => hcm_ne_a θ (Set.mem_singleton_iff.mp h)))
  -- derivWithin γ (Icc 0 1) is continuous on Icc 0 1
  have hdγ : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  -- γ is continuous on Icc 0 1
  have hγcts : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  -- deriv (circleMap a ε) is continuous (circleMap is smooth)
  have hdcm : Continuous (deriv (circleMap a ε)) :=
    (contDiff_circleMap a ε (n := ⊤)).continuous_deriv le_top
  -- Assemble: uncurry f p = f p.1 p.2
  change ContinuousOn (fun p : ℝ × ℝ =>
    derivWithin γ (Set.Icc (0:ℝ) 1) p.1 *
      (deriv (circleMap a ε) p.2 •
        (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1))))
    (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi))
  have hsmul : ∀ p : ℝ × ℝ,
      deriv (circleMap a ε) p.2 • (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1)) =
      deriv (circleMap a ε) p.2 * (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1)) :=
    fun p => smul_eq_mul _ _
  simp_rw [hsmul]
  refine ContinuousOn.mul ?_ ?_
  · exact hdγ.comp continuousOn_fst (fun p hp => hp.1)
  · refine ContinuousOn.mul ?_ ?_
    · exact hdcm.continuousOn.comp continuousOn_snd (fun p _ => Set.mem_univ _)
    · refine ContinuousOn.div ?_ ?_ ?_
      · exact hQ_cts.continuousOn.comp continuousOn_snd (fun p _ => Set.mem_univ _)
      · refine ContinuousOn.sub ?_ ?_
        · exact (continuous_circleMap a ε).continuousOn.comp
            continuousOn_snd (fun p _ => Set.mem_univ _)
        · exact hγcts.comp continuousOn_fst (fun p hp => hp.1)
      · intro p hp
        exact hne p hp

/-- `deriv γ` and `derivWithin γ (Set.Icc 0 1)` induce the same Q-kernel integrand almost
everywhere on `(Ioc 0 1) × (Ioc 0 2π)`. They coincide on `Ioo 0 1` (where `Set.Icc 0 1` is
a neighbourhood), and the exceptional set `{1} × ℝ` has product measure zero. -/
theorem q_kernel_deriv_eq_deriv_within_ae_prod
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (_hR : 0 < R)
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (_hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (_hclosed : γ 0 = γ 1)
    {ε : ℝ} (_hε_pos : 0 < ε) (_hε_R : ε < R)
    (_hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    (Function.uncurry (fun (t θ : ℝ) =>
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
      =ᵐ[((MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1)).prod
          (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) (2 * Real.pi))))]
      (Function.uncurry (fun (t θ : ℝ) =>
        derivWithin γ (Set.Icc (0:ℝ) 1) t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))))) := by
  simp only [Filter.EventuallyEq, Function.uncurry]
  rw [MeasureTheory.ae_iff]
  have hm : MeasurableSet (Set.univ \ Set.Ioo (0:ℝ) 1) :=
    MeasurableSet.univ.diff measurableSet_Ioo
  -- (ℝ \ Ioo 0 1) ∩ Ioc 0 1 = {1}, so the Ioc-restricted Lebesgue measure is 0 there
  have h0 : (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1))
            (Set.univ \ Set.Ioo (0:ℝ) 1) = 0 := by
    rw [MeasureTheory.Measure.restrict_apply hm]
    have hset : (Set.univ \ Set.Ioo (0:ℝ) 1) ∩ Set.Ioc (0:ℝ) 1 = {(1:ℝ)} := by
      ext x
      simp only [Set.mem_inter_iff, Set.mem_diff, Set.mem_univ, true_and, Set.mem_Ioo,
                 not_and_or, not_lt, Set.mem_Ioc, Set.mem_singleton_iff]
      constructor
      · rintro ⟨h | h, h1, h2⟩
        · linarith
        · exact le_antisymm h2 h
      · rintro rfl; exact ⟨Or.inr le_rfl, zero_lt_one, le_rfl⟩
    rw [hset]; simp
  -- bad set ⊆ (ℝ \ Ioo 0 1) × univ: if t ∈ Ioo 0 1 then Icc 0 1 ∈ nhds t
  -- so derivWithin γ (Icc 0 1) t = deriv γ t, contradicting membership in bad set
  apply MeasureTheory.measure_mono_null
      (show {p : ℝ × ℝ | ¬(deriv γ p.1 * (deriv (circleMap a ε) p.2 •
                (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1))) =
              derivWithin γ (Set.Icc 0 1) p.1 * (deriv (circleMap a ε) p.2 •
                (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1))))}
          ⊆ (Set.univ \ Set.Ioo (0:ℝ) 1) ×ˢ Set.univ by
        intro ⟨t, θ⟩ ht
        simp only [Set.mem_setOf_eq] at ht
        simp only [Set.mem_prod, Set.mem_diff, Set.mem_univ, true_and, and_true,
                   Set.mem_Ioo, not_and_or, not_lt]
        by_contra h
        rw [not_or] at h
        obtain ⟨h1, h2⟩ := h
        rw [not_le] at h1 h2
        exact ht (by congr 1; exact (derivWithin_of_mem_nhds (Icc_mem_nhds h1 h2)).symm))
  simp only [MeasureTheory.Measure.prod_prod]
  rw [h0, zero_mul]

/-- The Q-kernel integrand
`(t, θ) ↦ deriv γ t * (deriv (circleMap a ε) θ • (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))`
is integrable on `(volume.restrict (Ioc 0 1)).prod (volume.restrict (Ioc 0 2π))`.
The proof uses `q_kernel_aux_continuous_on_icc` to obtain integrability of the auxiliary
`derivWithin`-based integrand on the compact set `[0,1] × [0, 2π]`, then transfers via
`q_kernel_deriv_eq_deriv_within_ae_prod`. -/
theorem q_kernel_integrand_integrable
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_R : ε < R)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    MeasureTheory.Integrable
      (Function.uncurry (fun (t θ : ℝ) =>
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
      ((MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1)).prod
       (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) (2 * Real.pi)))) := by
  have h_cont :=
    q_kernel_aux_continuous_on_icc hR hQ_an hP hP_tendsto hP_rep
      hγ h_avoid hclosed hε_pos hε_R hε_sep
  have h_eq :=
    q_kernel_deriv_eq_deriv_within_ae_prod hR hQ_an hP hP_tendsto hP_rep
      hγ h_avoid hclosed hε_pos hε_R hε_sep
  have h_int : MeasureTheory.IntegrableOn _
      (Set.Ioc (0:ℝ) 1 ×ˢ Set.Ioc (0:ℝ) (2 * Real.pi))
      (MeasureTheory.volume.prod MeasureTheory.volume) :=
    (h_cont.integrableOn_compact (isCompact_Icc.prod isCompact_Icc)).mono_set
      (Set.prod_mono Set.Ioc_subset_Icc_self Set.Ioc_subset_Icc_self)
  rw [MeasureTheory.Measure.prod_restrict] at h_eq ⊢
  exact h_int.congr h_eq.symm

/-- The double interval integral
`∫ t in [0,1], ∫ θ in [0, 2π], deriv γ t * (deriv (circleMap a ε) θ • (Q … / (… - γ t)))`
equals the same integral with the order of integration swapped. This follows from
`MeasureTheory.integral_integral_swap` using joint integrability given by
`q_kernel_integrand_integrable`. -/
theorem q_kernel_double_fubini_swap
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_R : ε < R)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    (∫ t in (0:ℝ)..1, ∫ θ in (0:ℝ)..(2 * Real.pi),
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))))
      = ∫ θ in (0:ℝ)..(2 * Real.pi), ∫ t in (0:ℝ)..1,
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))) := by
  have h2pi : (0:ℝ) ≤ 2 * Real.pi := by positivity
  have h_int :=
    q_kernel_integrand_integrable hR hQ_an hP hP_tendsto hP_rep
      hγ h_avoid hclosed hε_pos hε_R hε_sep
  simp_rw [intervalIntegral.integral_of_le zero_le_one, intervalIntegral.integral_of_le h2pi]
  exact MeasureTheory.integral_integral_swap h_int

/-- Rewriting the path integral `∫ t, deriv γ t * ∮ w in C(a, ε), Q w / (w - γ t)` as a double
interval integral: unfolds `∮` as `∫ θ in [0, 2π]` via `circleIntegral`, then factors
`deriv γ t` inside using `intervalIntegral.integral_const_mul`. -/
theorem q_kernel_integral_circleIntegral_eq_double_integral
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (_hR : 0 < R)
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (_hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (_hclosed : γ 0 = γ 1)
    {ε : ℝ} (_hε_pos : 0 < ε) (_hε_R : ε < R)
    (_hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    (∫ t in (0:ℝ)..1, deriv γ t * (∮ w in C(a, ε), Q w / (w - γ t)))
      = ∫ t in (0:ℝ)..1, ∫ θ in (0:ℝ)..(2 * Real.pi),
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))) := by
  congr 1
  ext t
  simp only [circleIntegral, smul_eq_mul]
  exact (intervalIntegral.integral_const_mul (deriv γ t) _).symm

/-- Rewriting the double interval integral `∫ θ in [0, 2π], ∫ t in [0, 1], f t θ` back as a
circle integral: for each fixed `θ`, pulls `deriv (circleMap a ε) θ * Q (circleMap a ε θ)` out
of the inner `t`-integral via `intervalIntegral.integral_const_mul`, then refolds
`∫ θ in [0, 2π]` as `∮ w in C(a, ε)`. -/
theorem q_kernel_double_integral_eq_circleIntegral
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (_hR : 0 < R)
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (_hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (_hclosed : γ 0 = γ 1)
    {ε : ℝ} (_hε_pos : 0 < ε) (_hε_R : ε < R)
    (_hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    (∫ θ in (0:ℝ)..(2 * Real.pi), ∫ t in (0:ℝ)..1,
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))))
      = ∮ w in C(a, ε), Q w * (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t)) := by
  simp only [circleIntegral, smul_eq_mul]
  congr 1; ext θ
  have key : ∀ t : ℝ,
      deriv γ t * (deriv (circleMap a ε) θ * (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))) =
      (deriv (circleMap a ε) θ * Q (circleMap a ε θ)) *
        (deriv γ t / (circleMap a ε θ - γ t)) :=
    fun t => by ring
  simp_rw [key]
  have factored : ∫ t in (0:ℝ)..1,
      deriv (circleMap a ε) θ * Q (circleMap a ε θ) *
        (deriv γ t / (circleMap a ε θ - γ t)) =
      deriv (circleMap a ε) θ * Q (circleMap a ε θ) *
        ∫ t in (0:ℝ)..1, deriv γ t / (circleMap a ε θ - γ t) :=
    intervalIntegral.integral_const_mul _ _
  rw [factored]
  ring

/-- **Fubini swap for circle path integrals**: for a meromorphic function `Q` analytic on
`ℂ \ {a}`, a `C¹` closed path `γ : ℝ → ℂ` on `[0, 1]` avoiding `a`, and a circle `C(a, ε)`
lying strictly inside `γ`,
$$\int_0^1 (\partial_t \gamma)(t) \cdot \oint_{C(a,\varepsilon)} \frac{Q(w)}{w - \gamma(t)} \,
  dw \, dt
  = \oint_{C(a,\varepsilon)} Q(w) \cdot \int_0^1 \frac{(\partial_t \gamma)(t)}{w - \gamma(t)} \,
  dt \, dw.$$
The proof chains `q_kernel_integral_circleIntegral_eq_double_integral`,
`q_kernel_double_fubini_swap`, and `q_kernel_double_integral_eq_circleIntegral`. -/
theorem fubini_swap_circle_path_q
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_R : ε < R)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    (∫ t in (0:ℝ)..1, deriv γ t * (∮ w in C(a, ε), Q w / (w - γ t)))
      = ∮ w in C(a, ε), Q w * (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t)) := by
  have h_lhs :=
    q_kernel_integral_circleIntegral_eq_double_integral hR hQ_an hP hP_tendsto hP_rep
      hγ h_avoid hclosed hε_pos hε_R hε_sep
  have h_fubini :=
    q_kernel_double_fubini_swap hR hQ_an hP hP_tendsto hP_rep
      hγ h_avoid hclosed hε_pos hε_R hε_sep
  have h_rhs :=
    q_kernel_double_integral_eq_circleIntegral hR hQ_an hP hP_tendsto hP_rep
      hγ h_avoid hclosed hε_pos hε_R hε_sep
  exact h_lhs.trans (h_fubini.trans h_rhs)

end Library.Analysis.ResidueTheorem.FubiniCirclePath
