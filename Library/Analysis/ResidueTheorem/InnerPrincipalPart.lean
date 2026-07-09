import Library.Analysis.ResidueTheorem.CauchyIntegralDiff
import Library.Analysis.ResidueTheorem.CauchyKernelDecay
import Library.Analysis.ResidueTheorem.CauchyKernelSplit
import Library.Analysis.ResidueTheorem.CircleIntegralAnnulus

open Library.Analysis.ResidueTheorem.CauchyIntegralDiff
open Library.Analysis.ResidueTheorem.CauchyKernelDecay
open Library.Analysis.ResidueTheorem.CauchyKernelSplit
open Library.Analysis.ResidueTheorem.CircleIntegralAnnulus

/-!
# Inner Principal Part

This file constructs the **inner principal part** of a meromorphic function: given `f` analytic
on a punctured ball `Metric.ball z₀ R \ {z₀}`, we produce a function `P : ℂ → ℂ` analytic on
`ℂ \ {z₀}`, tending to zero along the cocompact filter, and satisfying
`P z = -((2πi)⁻¹ · ∮ w in C(z₀, ε), f w / (w - z))` for any sufficiently small `ε > 0`.

## Main statements

- `integrand_radius_indep`: the circle integral of the Cauchy kernel `f w / (w - z)` is
  independent of the radius when the radius is smaller than `dist z z₀`.
- `exists_inner_part_formula`: existence of a function `P` satisfying the inner integral formula.
- `inner_principal_part_exists`: the inner principal part `P` is analytic on `ℂ \ {z₀}` and
  tends to zero at infinity.

## Implementation notes

The key step is `integrand_radius_indep`, which uses `kernel_analytic_on_inner_ball` and the
annulus-independence lemma `circle_integral_eq_two_radii` to show that the inner circle integral
does not depend on the choice of radius.
-/

namespace Library.Analysis.ResidueTheorem.InnerPrincipalPart

/-- For a function `P` satisfying the inner integral formula on small circles around `z₀`,
`P` is eventually equal (in the `Filter.cocompact ℂ` filter) to the fixed Cauchy integral
over the circle of radius `R / 2`. This follows by applying the formula at `ε = R / 2` for
all `z` outside the closed ball of radius `R / 2`. -/
theorem inner_part_eventually_eq_cocompact
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    P =ᶠ[Filter.cocompact ℂ]
      (fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, R/2), f w / (w - z))) := by
  rw [Filter.eventuallyEq_iff_exists_mem]
  refine ⟨{z | R/2 < dist z z₀}, ?_, ?_⟩
  · rw [Filter.mem_cocompact]
    exact ⟨Metric.closedBall z₀ (R/2), isCompact_closedBall z₀ (R/2),
      fun z hz => by
        simp only [Set.mem_compl_iff, Metric.mem_closedBall, not_le] at hz; exact hz⟩
  · intro z hz
    simp only [Set.mem_setOf_eq] at hz
    have hzne : z ≠ z₀ := by
      intro h; subst h; simp at hz; linarith [half_pos hR]
    exact hP z hzne (R/2) (half_pos hR) hz (half_lt_self hR)

/-- **Cauchy annulus decomposition**: for `f` analytic on the punctured ball `B(z₀, R) \ {z₀}`,
if `g z` equals the outer Cauchy integral over a circle of radius `r ∈ (dist z z₀, R)` and
`P z` equals the (negated) inner Cauchy integral over a circle of radius `ε < dist z z₀`,
then `f z = g z + P z` for all `z ∈ B(z₀, R) \ {z₀}`.

This is the key decomposition underlying the residue theorem: `f` splits into an analytic
outer part (the Cauchy integral) and an inner principal part (the negative inner integral). -/
theorem cauchy_annulus_sum_formula
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (g P : ℂ → ℂ)
    (hg_eq : ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
      g z = (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, r), f w / (w - z))
    (hP_eq : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
      P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, ε), f w / (w - z))) :
    ∀ z ∈ Metric.ball z₀ R \ {z₀}, f z = g z + P z := by
  intro z hz
  obtain ⟨hzB, hzS⟩ := hz
  have hzNe : z ≠ z₀ := fun h => hzS (by simp [h])
  have hd_lt_R : dist z z₀ < R := Metric.mem_ball.mp hzB
  have hd_pos : 0 < dist z z₀ := dist_pos.mpr hzNe
  set r : ℝ := (dist z z₀ + R) / 2 with hr_def
  set ε : ℝ := dist z z₀ / 2 with hε_def
  have hr_lb : dist z z₀ < r := by linarith [hr_def]
  have hr_ub : r < R := by linarith [hr_def]
  have hε_pos : 0 < ε := by linarith [hε_def]
  have hε_lt_d : ε < dist z z₀ := by linarith [hε_def]
  have h_main := annulus_residue_diff hR hf hzB hzNe hr_lb hr_ub hε_pos hε_lt_d
  rw [hg_eq z hzB r hr_lb hr_ub, hP_eq z hzNe ε hε_pos hε_lt_d (lt_trans hε_lt_d hd_lt_R)]
  field_simp
  linear_combination -h_main

/-- For each `z ≠ z₀`, the inner principal part `P` agrees with the Cauchy integral over a
fixed small circle in a neighbourhood of `z`. Specifically, there exists `ε > 0` with
`ε < R` and `ε < dist z z₀` such that `P =ᶠ[nhds z] fun ζ => -((2πi)⁻¹ · ∮ C(z₀, ε), ·)`.

This local constancy of the inner formula is the key input for differentiability of `P`. -/
theorem inner_part_eventually_eq_nhds
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (_hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (z : ℂ) (hzne : z ≠ z₀) :
    ∃ ε : ℝ, 0 < ε ∧ ε < R ∧ ε < dist z z₀ ∧
      P =ᶠ[nhds z]
        (fun ζ => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - ζ))) := by
  have hdist : 0 < dist z z₀ := by rwa [dist_pos]
  refine ⟨min (dist z z₀ / 2) (R / 2), ?_, ?_, ?_, ?_⟩
  · positivity
  · exact lt_of_le_of_lt (min_le_right _ _) (by linarith)
  · exact lt_of_le_of_lt (min_le_left _ _) (by linarith)
  · apply Filter.Eventually.mono
        (Metric.ball_mem_nhds z (show (0 : ℝ) < dist z z₀ / 4 by linarith))
    intro ζ hζ
    have hζball : dist ζ z < dist z z₀ / 4 := Metric.mem_ball.mp hζ
    have hεpos : 0 < min (dist z z₀ / 2) (R / 2) := by positivity
    have hε_lt_distζ : min (dist z z₀ / 2) (R / 2) < dist ζ z₀ := by
      apply lt_of_le_of_lt (min_le_left _ _)
      have h1 : dist z z₀ ≤ dist z ζ + dist ζ z₀ := dist_triangle z ζ z₀
      have h2 : dist z ζ < dist z z₀ / 4 := by rwa [dist_comm]
      linarith
    have hζne : ζ ≠ z₀ := by
      intro h; rw [h, dist_comm] at hζball; linarith
    exact hP ζ hζne _ hεpos hε_lt_distζ
        (lt_of_le_of_lt (min_le_right _ _) (by linarith))

/-- The Cauchy kernel `fun w => f w / (w - z)` is analytic on the punctured ball
`Metric.ball z₀ (min R (dist z z₀)) \ {z₀}`, provided `f` is analytic on `B(z₀, R) \ {z₀}`
and `z ≠ z₀`. The radius `min R (dist z z₀)` ensures `w - z ≠ 0` throughout the ball. -/
theorem kernel_analytic_on_inner_ball
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (_hz : z ≠ z₀) :
    AnalyticOn ℂ (fun w => f w / (w - z))
      (Metric.ball z₀ (min R (dist z z₀)) \ {z₀}) := by
  apply AnalyticOn.div
  · exact hf.mono (Set.diff_subset_diff_left
        (Metric.ball_subset_ball (min_le_left R (dist z z₀))))
  · exact analyticOn_id.sub analyticOn_const
  · intro w hw
    have hlt : dist w z₀ < dist z z₀ :=
      (Metric.mem_ball.mp hw.1).trans_le (min_le_right R _)
    intro heq
    rw [sub_eq_zero] at heq
    rw [heq] at hlt
    exact lt_irrefl _ hlt

/-- The circle integral `∮ w in C(z₀, ε), f w / (w - z)` does not depend on `ε`, provided
`0 < ε < dist z z₀` and `ε < R`. This follows from the analyticity of the Cauchy kernel on
the punctured ball of radius `min R (dist z z₀)` and the homotopy-invariance of circle integrals
(`circle_integral_eq_two_radii`). -/
theorem integrand_radius_indep
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hz : z ≠ z₀)
    {ε₁ ε₂ : ℝ} (hε₁ : 0 < ε₁) (hε₂ : 0 < ε₂)
    (hε₁d : ε₁ < dist z z₀) (hε₂d : ε₂ < dist z z₀)
    (hε₁R : ε₁ < R) (hε₂R : ε₂ < R) :
    (∮ w in C(z₀, ε₁), f w / (w - z)) = (∮ w in C(z₀, ε₂), f w / (w - z)) := by
  set ρ : ℝ := min R (dist z z₀) with hρ_def
  have hzdist : (0 : ℝ) < dist z z₀ := dist_pos.mpr hz
  have hρ_pos : 0 < ρ := lt_min hR hzdist
  have hε₁ρ : ε₁ < ρ := lt_min hε₁R hε₁d
  have hε₂ρ : ε₂ < ρ := lt_min hε₂R hε₂d
  have hgan : AnalyticOn ℂ (fun w => f w / (w - z))
      (Metric.ball z₀ ρ \ {z₀}) := kernel_analytic_on_inner_ball hf hz
  exact circle_integral_eq_two_radii hgan hgan hε₁ hε₁ρ hε₂ hε₂ρ

/-- There exists a function `P : ℂ → ℂ` satisfying the inner principal part integral formula:
for all `z ≠ z₀` and all `ε` with `0 < ε < dist z z₀` and `ε < R`,
`P z = -((2πi)⁻¹ · ∮ w in C(z₀, ε), f w / (w - z))`.

The witness is `P z = -((2πi)⁻¹ · ∮ w in C(z₀, min R (dist z z₀) / 2), f w / (w - z))`,
and radius independence (`integrand_radius_indep`) shows it satisfies the formula for any `ε`. -/
theorem exists_inner_part_formula
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ P : ℂ → ℂ,
      ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)) := by
  refine ⟨fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, min R (dist z z₀) / 2), f w / (w - z)), ?_⟩
  intro z hz ε hε hεd hεR
  have hd : 0 < dist z z₀ := dist_pos.mpr hz
  have hm_pos : 0 < min R (dist z z₀) := lt_min hR hd
  have hm_half_pos : 0 < min R (dist z z₀) / 2 := by linarith
  have hm_half_lt_d : min R (dist z z₀) / 2 < dist z z₀ := by
    have := min_le_right R (dist z z₀); linarith
  have hm_half_lt_R : min R (dist z z₀) / 2 < R := by
    have := min_le_left R (dist z z₀); linarith
  have hindep : (∮ w in C(z₀, min R (dist z z₀) / 2), f w / (w - z)) =
                (∮ w in C(z₀, ε), f w / (w - z)) :=
    integrand_radius_indep hR hf hz hm_half_pos hε
      hm_half_lt_d hεd hm_half_lt_R hεR
  simp only [hindep]

/-- The inner principal part `P` tends to zero along `Filter.cocompact ℂ`. The proof picks a
fixed radius `R / 2`, rewrites `P z` via `hP` for `z` far from `z₀` (using
`inner_part_eventually_eq_cocompact`), and concludes with `inner_integral_tendsto_zero` via
`Filter.Tendsto.congr'`. -/
theorem inner_part_tendsto_zero_cocompact
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) := by
  have h_eq : P =ᶠ[Filter.cocompact ℂ]
      (fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, R/2), f w / (w - z))) :=
    inner_part_eventually_eq_cocompact hR hf P hP
  have h_tendsto : Filter.Tendsto
      (fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, R/2), f w / (w - z)))
      (Filter.cocompact ℂ) (nhds 0) :=
    inner_integral_tendsto_zero hR hf P hP
  exact h_tendsto.congr' h_eq.symm

/-- The inner principal part `P` is complex-differentiable on `Set.univ \ {z₀}`. For each
`z ≠ z₀`, `inner_part_eventually_eq_nhds` provides a local neighbourhood on which `P` equals
the Cauchy integral `fun ζ => -((2πi)⁻¹ · ∮ C(z₀, ε), f w / (w - ζ))`, which is differentiable
at `z` by `cauchy_kernel_diff_at_outside`. -/
theorem inner_part_differentiableOn_compl_singleton
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    DifferentiableOn ℂ P (Set.univ \ {z₀}) := by
  intro z hz
  have hzne : z ≠ z₀ := fun h => hz.2 (h ▸ rfl)
  obtain ⟨ε, hε0, hεR, hεd, hPeq⟩ :=
    inner_part_eventually_eq_nhds hR hf P hP z hzne
  have h_diff :=
    cauchy_kernel_diff_at_outside hR hf ε hε0 hεR z hzne hεd
  exact ((hPeq.differentiableAt_iff).mpr h_diff).differentiableWithinAt

/-- The inner principal part `P` is analytic on `Set.univ \ {z₀}`. This follows from
`inner_part_differentiableOn_compl_singleton` and the fact that `Set.univ \ {z₀}` is open,
via `DifferentiableOn.analyticOn`. -/
theorem inner_part_analyticOn_compl_singleton
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    AnalyticOn ℂ P (Set.univ \ {z₀}) := by
  have hdiff : DifferentiableOn ℂ P (Set.univ \ {z₀}) :=
    inner_part_differentiableOn_compl_singleton hR hf P hP
  have hopen : IsOpen (Set.univ \ {z₀}) := by
    rw [Set.diff_eq, Set.univ_inter]; exact isOpen_compl_singleton
  exact hdiff.analyticOn hopen

/-- **Inner principal part existence**: for `f` analytic on the punctured ball `B(z₀, R) \ {z₀}`,
there exists `P : ℂ → ℂ` that is analytic on `ℂ \ {z₀}`, tends to zero at infinity (along
`Filter.cocompact ℂ`), and satisfies the inner Cauchy integral formula
`P z = -((2πi)⁻¹ · ∮ w in C(z₀, ε), f w / (w - z))` for all `z ≠ z₀` and `ε < dist z z₀`. -/
theorem inner_principal_part_exists
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (P : ℂ → ℂ), AnalyticOn ℂ P (Set.univ \ {z₀}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)) := by
  obtain ⟨P, hP_eq⟩ := exists_inner_part_formula hR hf
  refine ⟨P, ?_, ?_, hP_eq⟩
  · exact inner_part_analyticOn_compl_singleton hR hf P hP_eq
  · exact inner_part_tendsto_zero_cocompact hR hf P hP_eq

end Library.Analysis.ResidueTheorem.InnerPrincipalPart
