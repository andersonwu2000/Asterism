import Mathlib.Analysis.Complex.Liouville
import Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
import Library.Analysis.ResidueTheorem.FubiniCirclePath
import Library.Analysis.ResidueTheorem.HolomorphicPart
import Library.Analysis.ResidueTheorem.InnerPrincipalPart
import Library.Analysis.ResidueTheorem.PrincipalPartExtraction
import Library.Analysis.ResidueTheorem.WindingNumberInt
import Library.Analysis.ResidueTheorem.WindingNumberPath

/-!
# Winding number and circle integrals for the residue theorem

This file assembles the key steps connecting path integrals along a closed curve `γ`
to circle integrals and winding numbers, culminating in the result that a meromorphic
function with zero residue at its only singularity integrates to zero along any closed
path avoiding that singularity.

## Main statements

- `eq_of_analyticOn_punctured_tendsto_cocompact`: two functions analytic on `ℂ \ {a}`
  that agree near `a` up to a holomorphic correction and both decay at infinity must
  agree on all of `ℂ \ {a}`.
- `q_eq_inner_cauchy_principal_part`: every `Q` analytic on `ℂ \ {a}` with decay at
  infinity equals its inner Cauchy principal part `P` on `ℂ \ {a}`.
- `path_int_p_eq_winding_circle_int_q`: the path integral of `P` along `γ` equals the
  winding number of `γ` around `a` times the circle integral of `Q`.
- `analytic_residue_zero_decay_closed_loop_zero`: if `Q` is analytic on `ℂ \ {a}`,
  decays at infinity, and `residue Q a = 0`, then the contour integral of `Q` along
  any closed curve avoiding `a` is zero.
-/

open Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
open Library.Analysis.ResidueTheorem.FubiniCirclePath
open Library.Analysis.ResidueTheorem.HolomorphicPart
open Library.Analysis.ResidueTheorem.InnerPrincipalPart
open Library.Analysis.ResidueTheorem.PrincipalPartExtraction
open Library.Analysis.ResidueTheorem.WindingNumberInt
open Library.Analysis.ResidueTheorem.WindingNumberPath

namespace Library.Analysis.ResidueTheorem.WindingCircleIntegral

/-- The glued function `w ↦ if w = a then g a else Q w - P w` tends to zero along
the cocompact filter. Since `{a}` is compact, the glued function agrees with `Q - P`
cocompactly; `Q - P → 0` follows from `hQ_decay.sub hP_decay`, and
`Filter.tendsto_congr'` closes the goal. -/
theorem glued_qmp_tendsto_cocompact_zero
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (_hR : 0 < R)
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (_hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_decay : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (_hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (_h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w) :
    Filter.Tendsto (fun w => if w = a then g a else Q w - P w)
      (Filter.cocompact ℂ) (nhds 0) := by
  have h_sub : Filter.Tendsto (fun w => Q w - P w) (Filter.cocompact ℂ) (nhds 0) := by
    simpa using hQ_decay.sub hP_decay
  have h_compact : IsCompact ({a} : Set ℂ) := isCompact_singleton
  have h_event : ∀ᶠ w in Filter.cocompact ℂ, w ∉ ({a} : Set ℂ) :=
    h_compact.compl_mem_cocompact
  have h_eq : (fun w => if w = a then g a else Q w - P w) =ᶠ[Filter.cocompact ℂ]
              (fun w => Q w - P w) := by
    filter_upwards [h_event] with w hw
    have hwa : w ≠ a := by simpa using hw
    rw [if_neg hwa]
  exact (Filter.tendsto_congr' h_eq).mpr h_sub

/-- The glued function `w ↦ if w = a then g a else Q w - P w` is differentiable at `a`.
On `Metric.ball a R` the glued function agrees with `g` (by definition at `a` and by
`h_diff_eq` off `a`), so differentiability at `a` is inherited from `hg_an` via
`Filter.EventuallyEq.differentiableAt_iff`. -/
theorem glued_qmp_diff_at_pole
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w) :
    DifferentiableAt ℂ (fun w => if w = a then g a else Q w - P w) a := by
  have hg_diff : DifferentiableAt ℂ g a :=
    hg_an.differentiableOn.differentiableAt (Metric.ball_mem_nhds a hR)
  have heq : (fun w => if w = a then g a else Q w - P w) =ᶠ[nhds a] g := by
    filter_upwards [Metric.ball_mem_nhds a hR] with w hw
    by_cases hwa : w = a
    · simp only [hwa, ↓reduceIte]
    · rw [if_neg hwa]; exact h_diff_eq w ⟨hw, hwa⟩
  exact (Filter.EventuallyEq.differentiableAt_iff heq).mpr hg_diff

/-- The glued function `w ↦ if w = a then g a else Q w - P w` is differentiable at
every `z ≠ a`. Near `z` the glued function agrees with `Q - P`, which is differentiable
because `Q` and `P` are analytic on `ℂ \ {a}`. -/
theorem glued_qmp_diff_off_a
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (_hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (_h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w)
    (z : ℂ) (hz : z ≠ a) :
    DifferentiableAt ℂ (fun w => if w = a then g a else Q w - P w) z := by
  have hz_mem : z ∈ Set.univ \ {a} := ⟨Set.mem_univ z, by simpa using hz⟩
  have hopen : IsOpen (Set.univ \ {a} : Set ℂ) := isOpen_univ.sdiff isClosed_singleton
  have hQ_diff : DifferentiableAt ℂ Q z :=
    hQ_an.differentiableOn.differentiableAt (hopen.mem_nhds hz_mem)
  have hP_diff : DifferentiableAt ℂ P z :=
    hP_an.differentiableOn.differentiableAt (hopen.mem_nhds hz_mem)
  have hQP_diff : DifferentiableAt ℂ (fun w => Q w - P w) z := hQ_diff.sub hP_diff
  have hne_nhd : ({a} : Set ℂ)ᶜ ∈ nhds z := isClosed_singleton.isOpen_compl.mem_nhds hz
  exact hQP_diff.congr_of_eventuallyEq (by
    filter_upwards [hne_nhd] with w hw
    have hwne : w ≠ a := by simpa using hw
    rw [if_neg hwne])

/-- The glued function `w ↦ if w = a then g a else Q w - P w` is entire. This combines
`glued_qmp_diff_at_pole` at `a` and `glued_qmp_diff_off_a` at every `z ≠ a`. -/
theorem glued_qmp_differentiable_entire
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hP_decay : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w) :
    Differentiable ℂ (fun w => if w = a then g a else Q w - P w) := by
  intro z
  by_cases hz : z = a
  · have h_at_a : DifferentiableAt ℂ (fun w => if w = a then g a else Q w - P w) a :=
      glued_qmp_diff_at_pole hR hQ_an hP_an hg_an h_diff_eq
    simpa [hz] using h_at_a
  · exact glued_qmp_diff_off_a hR hQ_an hP_an hg_an h_diff_eq z hz

/-- Two functions `Q`, `P` analytic on `ℂ \ {a}`, decaying at infinity, and satisfying
`Q w - P w = g w` for a holomorphic `g` near `a`, must agree on all of `ℂ \ {a}`.
The glued extension of `Q - P` to `a` is entire and decays at infinity, so Liouville
forces it to be identically zero. -/
theorem eq_of_analyticOn_punctured_tendsto_cocompact
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_decay : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), Q z = P z := by
  set h_ext : ℂ → ℂ := fun w => if w = a then g a else Q w - P w with hh_ext
  have h_diff : Differentiable ℂ h_ext :=
    glued_qmp_differentiable_entire hR hQ_an hQ_decay hP_an hP_decay hg_an h_diff_eq
  have h_decay : Filter.Tendsto h_ext (Filter.cocompact ℂ) (nhds 0) :=
    glued_qmp_tendsto_cocompact_zero hR hQ_an hQ_decay hP_an hP_decay hg_an h_diff_eq
  intro z hz
  have hz_ne : z ≠ a := by
    intro h
    exact hz.2 (by simp [h])
  have h_zero : h_ext z = 0 := h_diff.apply_eq_of_tendsto_cocompact z h_decay
  have h_ext_eq : h_ext z = Q z - P z := by
    simp [hh_ext, hz_ne]
  have hsub : Q z - P z = 0 := by rw [← h_ext_eq]; exact h_zero
  exact sub_eq_zero.mp hsub

/-- Every `Q` analytic on `ℂ \ {a}` and decaying at infinity equals its inner Cauchy
principal part `P` on all of `ℂ \ {a}`. The principal part `P` is analytic on `ℂ \ {a}`,
decays at infinity, and satisfies the inner Cauchy integral representation
`P z = -((2πi)⁻¹ * ∮_{C(a,ε)} Q w / (w - z) dw)` for sufficiently small `ε`. -/
theorem q_eq_inner_cauchy_principal_part
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0)) :
    ∃ (P : ℂ → ℂ) (R : ℝ),
      0 < R ∧
      AnalyticOn ℂ P (Set.univ \ {a}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      (∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z))) ∧
      (∀ z ∈ Set.univ \ ({a} : Set ℂ), Q z = P z) := by
  have hR : (0 : ℝ) < 1 := by norm_num
  have hQ_an_ball : AnalyticOn ℂ Q (Metric.ball a 1 \ {a}) :=
    hQ_an.mono (fun w hw => ⟨Set.mem_univ _, hw.2⟩)
  have h_inner := inner_principal_part_exists hR hQ_an_ball
  have h_outer :=
    Library.Analysis.ResidueTheorem.HolomorphicPart.exists_analyticOn_cauchy_kernel
      hR hQ_an_ball
  obtain ⟨P, hP_an, hP_t, hP_eq⟩ := h_inner
  obtain ⟨g, hg_an, hg_eq⟩ := h_outer
  have hQg : ∀ w ∈ Metric.ball a 1 \ {a}, Q w = g w + P w :=
    cauchy_annulus_add_eq hR hQ_an_ball g P hg_eq hP_eq
  have h_diff_eq : ∀ w ∈ Metric.ball a 1 \ {a}, Q w - P w = g w := by
    intro w hw
    have hqw := hQg w hw
    linear_combination hqw
  have h_global : ∀ z ∈ Set.univ \ ({a} : Set ℂ), Q z = P z :=
    eq_of_analyticOn_punctured_tendsto_cocompact hR hQ_an hQ_decay hP_an hP_t hg_an h_diff_eq
  exact ⟨P, 1, hR, hP_an, hP_t, hP_eq, h_global⟩

/-- For `w` on `Metric.sphere a ε`, when `γ` is a closed `C¹` path avoiding `a` and
uniformly separated from `a` by more than `ε`, the path integral
`∫₀¹ γ'(t) / (w - γ t) dt` equals `-(2πi) · windingNumber γ a`.
Step (A): `path_int_eq_neg_winding_at_w` converts the integral to
`-(2πi) · windingNumber γ w`. Step (B): `winding_const_on_eps_sphere` shows
`windingNumber γ w = windingNumber γ a` by constancy on the `ε`-disk. -/
theorem inner_path_int_winding_q
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (_hR : 0 < R)
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (_hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) (_hε_R : ε < R)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    ∀ w ∈ Metric.sphere a ε,
      (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t))
        = -(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ a : ℂ) := by
  intro w hw
  have hA := path_int_eq_neg_winding_at_w hγ hclosed hε_sep w hw
  have hB := winding_const_on_eps_sphere hγ hclosed hε_pos hε_sep w hw
  rw [hA, hB]

/-- The path integral of the principal part `P` along `γ` equals
`windingNumber γ a · ∮_{C(a,ε)} Q w dw`. The proof uses
`fubini_swap_circle_path_q` to swap `∫₀¹` and `∮_{C(a,ε)}`, then
`inner_path_int_winding_q` to identify the inner integral with
`-(2πi) · windingNumber γ a` for each `w ∈ Metric.sphere a ε`. -/
theorem path_int_p_eq_winding_circle_int_q
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
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t)
      = (Complex.windingNumber γ a : ℂ) * (∮ w in C(a, ε), Q w) := by
  have h_fubini := fubini_swap_circle_path_q hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed
    hε_pos hε_R hε_sep
  have h_inner := inner_path_int_winding_q hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed
    hε_pos hε_R hε_sep
  have h_int_eq : (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t)
        = ∫ t in (0:ℝ)..1, -((2 * (Real.pi : ℂ) * Complex.I)⁻¹)
                            * (deriv γ t * (∮ w in C(a, ε), Q w / (w - γ t))) := by
    refine intervalIntegral.integral_congr ?_
    intro t ht
    rw [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1)] at ht
    change P (γ t) * deriv γ t = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹)
                            * (deriv γ t * (∮ w in C(a, ε), Q w / (w - γ t)))
    rw [hP_rep (γ t) (h_avoid t ht) ε hε_pos (hε_sep t ht) hε_R]
    ring
  have h_const_pull :
      (∫ t in (0:ℝ)..1, -((2 * (Real.pi : ℂ) * Complex.I)⁻¹)
                            * (deriv γ t * (∮ w in C(a, ε), Q w / (w - γ t))))
        = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹)
            * ∫ t in (0:ℝ)..1, deriv γ t * (∮ w in C(a, ε), Q w / (w - γ t)) :=
    intervalIntegral.integral_const_mul _ _
  rw [h_int_eq, h_const_pull, h_fubini]
  have hcong :
      (∮ w in C(a, ε), Q w * (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t)))
        = ∮ w in C(a, ε),
            (-(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ a : ℂ)) * Q w := by
    refine circleIntegral.integral_congr hε_pos.le ?_
    intro w hw
    change Q w * (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t))
          = (-(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ a : ℂ)) * Q w
    rw [h_inner w hw]; ring
  rw [hcong, circleIntegral.integral_const_mul]
  have h_ne : (2 * (Real.pi : ℂ) * Complex.I) ≠ 0 := by
    have hpi : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    exact mul_ne_zero (mul_ne_zero (by norm_num) hpi) Complex.I_ne_zero
  field_simp

/-- There exists `ε > 0` with `ε < R` such that `dist (γ t) a > ε` for all
`t ∈ [0, 1]`. The proof uses compactness of `[0, 1]` to find the minimizer `t₀` of
`t ↦ dist (γ t) a`, then takes `ε = min(dist (γ t₀) a / 2, R / 2)`. -/
theorem uniform_eps_separation_path_radius
    {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∃ ε : ℝ, 0 < ε ∧ ε < R ∧ ∀ t ∈ Set.Icc (0 : ℝ) 1, ε < dist (γ t) a := by
  have hcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have hpos : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 < dist (γ t) a :=
    fun t ht => dist_pos.mpr (h_avoid t ht)
  have hcont_dist : ContinuousOn (fun t => dist (γ t) a) (Set.Icc 0 1) :=
    fun t ht => (hcont t ht).dist continuousWithinAt_const
  have hne : (Set.Icc (0 : ℝ) 1).Nonempty := Set.nonempty_Icc.mpr zero_le_one
  obtain ⟨t₀, ht₀, hmin⟩ := isCompact_Icc.exists_isMinOn hne hcont_dist
  have hε_pos : 0 < dist (γ t₀) a := hpos t₀ ht₀
  refine ⟨min (dist (γ t₀) a / 2) (R / 2), lt_min (by linarith) (by linarith),
         min_lt_of_right_lt (by linarith), fun t ht => ?_⟩
  exact lt_of_le_of_lt (min_le_left _ _) (lt_of_lt_of_le (by linarith) (hmin ht))

/-- The circle integral `∮_{C(a,ε)} Q w dw` equals `2πi · residue Q a` for any `ε > 0`,
when `Q` is analytic on `ℂ \ {a}`. The proof unfolds `Complex.residue` (a classical
choice of radius) and applies `circle_integral_radius_indep_on_punctured_ball` to
transfer between the arbitrary `ε` and the chosen radius. -/
theorem circle_int_q_eq_two_pi_residue_at
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {ε : ℝ} (hε_pos : 0 < ε) :
    (∮ w in C(a, ε), Q w) = 2 * Real.pi * Complex.I * Complex.residue Q a := by
  have hQball : ∀ R : ℝ, 0 < R → AnalyticOn ℂ Q (Metric.ball a R \ {a}) := fun R _ =>
    hQ_an.mono (Set.diff_subset_diff_left (Set.subset_univ _))
  have hcond : ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ Q (Metric.ball a R \ {a}) :=
    ⟨1, one_pos, hQball 1 one_pos⟩
  simp only [Complex.residue, dif_pos hcond]
  set R_chosen := Classical.choose hcond with hR_def
  have hR_spec := Classical.choose_spec hcond
  have hR_pos : 0 < R_chosen := hR_spec.1
  have h2pi_ne : 2 * (Real.pi : ℂ) * Complex.I ≠ 0 := by
    have hpi : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    exact mul_ne_zero (mul_ne_zero (by norm_num) hpi) Complex.I_ne_zero
  have hcirc_eq : (∮ w in C(a, ε), Q w) = (∮ w in C(a, R_chosen / 2), Q w) := by
    by_cases hle : ε ≤ R_chosen / 2
    · exact circle_integral_radius_indep_on_punctured_ball (hR_spec.2) hε_pos hle (by linarith)
    · push Not at hle
      have hR2_pos : (0 : ℝ) < R_chosen / 2 := by linarith
      exact (circle_integral_radius_indep_on_punctured_ball
        (hQball (ε + 1) (by linarith)) hR2_pos (by linarith) (by linarith)).symm
  rw [hcirc_eq]
  field_simp [h2pi_ne]

/-- If `P` is the inner Cauchy principal part of `Q` at `a` and `residue Q a = 0`,
then `∫₀¹ P(γ t) · γ'(t) dt = 0` for every closed `C¹` curve `γ` avoiding `a`.
The proof picks a uniform separation `ε` via `uniform_eps_separation_path_radius`,
reduces the integral to `windingNumber γ a · ∮_{C(a,ε)} Q` via
`path_int_p_eq_winding_circle_int_q`, and evaluates the circle integral to
`2πi · residue Q a = 0` via `circle_int_q_eq_two_pi_residue_at`. -/
theorem inner_cauchy_part_path_int_zero_residue_zero
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hQ_res : Complex.residue Q a = 0)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) = 0 := by
  obtain ⟨ε, hε_pos, hε_R, hε_sep⟩ :=
    uniform_eps_separation_path_radius hR hγ h_avoid
  have h_path_eq :=
    path_int_p_eq_winding_circle_int_q hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed
      hε_pos hε_R hε_sep
  have h_circle_eq :=
    circle_int_q_eq_two_pi_residue_at hQ_an hε_pos
  rw [h_path_eq, h_circle_eq, hQ_res]
  ring

/-- **Main result**: if `Q` is analytic on `ℂ \ {a}`, decays to zero at infinity, and
satisfies `Complex.residue Q a = 0`, then the contour integral of `Q` along any
closed `C¹` curve `γ : [0, 1] → ℂ` avoiding `a` is zero. The proof extracts the inner
Cauchy principal part `P` via `q_eq_inner_cauchy_principal_part` (giving `Q = P` on
`ℂ \ {a}`), replaces `Q` by `P` in the integrand, and applies
`inner_cauchy_part_path_int_zero_residue_zero`. -/
theorem analytic_residue_zero_decay_closed_loop_zero
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hQ_res : Complex.residue Q a = 0)
    (γ : ℝ → ℂ)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0 := by
  obtain ⟨P, R, hR, hPan, hPtend, hPrep, hQeqP⟩ :=
    q_eq_inner_cauchy_principal_part hQ_an hQ_decay
  have hcong : ∀ t ∈ Set.uIcc (0:ℝ) 1,
      Q (γ t) * deriv γ t = P (γ t) * deriv γ t := by
    intro t ht
    rw [Set.uIcc_of_le zero_le_one] at ht
    have hγt : γ t ∈ Set.univ \ ({a} : Set ℂ) :=
      ⟨trivial, h_avoid t ht⟩
    rw [hQeqP (γ t) hγt]
  rw [intervalIntegral.integral_congr hcong]
  exact inner_cauchy_part_path_int_zero_residue_zero
    hR hQ_an hPan hPtend hPrep hQ_res hγ h_avoid hclosed

end Library.Analysis.ResidueTheorem.WindingCircleIntegral
