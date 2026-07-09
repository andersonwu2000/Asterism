import Library.Analysis.ResidueTheorem.WindingNumberInt

/-!
# Winding Number Formula

This module establishes the winding number integral formula for closed $C^1$ paths and
proves that the winding number is locally constant on connected components of the complement
of the path image.

## Main statements

- `winding_integral_formula`: for a closed $C^1$ path `γ` avoiding `a`, the log-derivative
  integral equals `2 * π * I * windingNumber γ a`.
- `winding_const_on_open_ball_off_image`: `Complex.windingNumber γ` is constant on any open
  ball disjoint from the image of `γ`.

## Implementation notes

Local constancy is proved by showing the parametric integral `w ↦ ∫₀¹ deriv γ t / (γ t - w)`
is continuous on the ball (dominated convergence with a compact-set bound), then applying the
discrete-image-on-connected-set principle: a continuous integer-valued function on a connected
set must be constant.
-/

open Library.Analysis.ResidueTheorem.WindingNumberInt

namespace Library.Analysis.ResidueTheorem.WindingNumberFormula

/-- **Winding number formula**: for a closed $C^1$ path `γ : ℝ → ℂ` avoiding `a : ℂ`,
the log-derivative integral over `[0, 1]` equals `2 * π * I * windingNumber γ a`. -/
theorem winding_integral_formula
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a))
      = 2 * Real.pi * Complex.I * (Complex.windingNumber γ a : ℂ) := by
  unfold Complex.windingNumber
  have h_exists : ∃ k : ℤ, (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) =
      2 * Real.pi * Complex.I * (k : ℂ) :=
    exists_winding_integer hγ hclosed h_avoid
  rw [dif_pos h_exists]
  exact Classical.choose_spec h_exists

/-- On a ball `Metric.ball z r` disjoint from the image of `γ`, the integrals with `deriv γ`
and `derivWithin γ (Set.Icc 0 1)` agree pointwise, since the two derivatives coincide
almost everywhere on `[0, 1]` (they differ only at the endpoints, a null set). -/
theorem intervalIntegral_deriv_eq_derivWithin_div
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hr : 0 < r)
    (_h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z) :
    ∀ w ∈ Metric.ball z r,
      (∫ t in (0:ℝ)..1, deriv γ t / (γ t - w)) =
      (∫ t in (0:ℝ)..1, derivWithin γ (Set.Icc 0 1) t / (γ t - w)) := by
  intro w _hw
  apply intervalIntegral.integral_congr_ae
  simp only [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
  rw [MeasureTheory.ae_iff]
  apply MeasureTheory.measure_mono_null _ (Real.volume_singleton (a := 1))
  intro t ht
  simp only [Set.mem_setOf_eq, Classical.not_imp] at ht
  obtain ⟨ht_mem, ht_ne⟩ := ht
  simp only [Set.mem_singleton_iff]
  by_contra h1
  exact ht_ne (by
    congr 1
    have htIoo : t ∈ Set.Ioo (0:ℝ) 1 := ⟨ht_mem.1, lt_of_le_of_ne ht_mem.2 h1⟩
    exact (derivWithin_of_mem_nhds (Icc_mem_nhds htIoo.1 htIoo.2)).symm)

/-- The Cauchy integrand `(w, t) ↦ derivWithin γ (Set.Icc 0 1) t / (γ t - w)` is jointly
continuous on `Metric.ball z r ×ˢ Set.Icc 0 1`. The numerator uses
`ContDiffOn.continuousOn_derivWithin`; the denominator is nonzero because `γ` avoids
`Metric.ball z r`. -/
theorem integrand_joint_continuous_on_ball_icc
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z) :
    ContinuousOn
      (fun p : ℂ × ℝ => derivWithin γ (Set.Icc 0 1) p.2 / (γ p.2 - p.1))
    (Metric.ball z r ×ˢ Set.Icc 0 1) := by
  apply ContinuousOn.div
  · exact (hγ.continuousOn_derivWithin (uniqueDiffOn_Icc zero_lt_one) le_rfl).comp
      continuous_snd.continuousOn (fun p hp => hp.2)
  · apply ContinuousOn.sub
    · exact hγ.continuousOn.comp continuous_snd.continuousOn (fun p hp => hp.2)
    · exact continuous_fst.continuousOn
  · intro ⟨w, t⟩ ⟨hw, ht⟩ heq
    have hdw : dist w z < r := Metric.mem_ball.mp hw
    have hdγ : r < dist (γ t) z := h_avoid t ht
    have hne : γ t ≠ w := by
      intro h
      have heqdist : dist (γ t) z = dist w z := by rw [h]
      linarith [heqdist ▸ hdγ]
    exact hne (sub_eq_zero.mp heq)

/-- If `f : ℂ → ℂ` is continuous on `Metric.ball z r` and satisfies
`f w = 2 * π * I * (n w : ℂ)` for an integer-valued function `n : ℂ → ℤ`, then `n` is
continuous on the ball. Since `Int.cast : ℤ → ℂ` is a topological embedding, continuity
of `f` lifts back to continuity of `n`. -/
theorem continuousOn_int_of_two_pi_I_mul_continuousOn
    {z : ℂ} {r : ℝ}
    (_hr : 0 < r)
    {f : ℂ → ℂ}
    (hf : ContinuousOn f (Metric.ball z r))
    {n : ℂ → ℤ}
    (hfn : ∀ w ∈ Metric.ball z r,
              f w = 2 * Real.pi * Complex.I * (n w : ℂ)) :
    ContinuousOn n (Metric.ball z r) := by
  have h2pi : (2 * ↑Real.pi * Complex.I : ℂ) ≠ 0 :=
    mul_ne_zero (mul_ne_zero (by norm_num) (by exact_mod_cast Real.pi_ne_zero)) Complex.I_ne_zero
  have hcast : ContinuousOn (fun w => (n w : ℂ)) (Metric.ball z r) := by
    apply (hf.div_const (2 * Real.pi * Complex.I)).congr
    intro w hw
    change (n w : ℂ) = f w / (2 * ↑Real.pi * Complex.I)
    rw [hfn w hw]
    field_simp [h2pi]
  intro w₀ hw₀
  have hndis : nhds (n w₀) = pure (n w₀) := congr_fun (nhds_discrete ℤ) (n w₀)
  change Filter.Tendsto n (nhdsWithin w₀ (Metric.ball z r)) (nhds (n w₀))
  rw [hndis, Filter.tendsto_pure]
  have hclose : ∀ᶠ w in nhdsWithin w₀ (Metric.ball z r), ‖(n w : ℂ) - (n w₀ : ℂ)‖ < 1 := by
    have hconst : ContinuousWithinAt (fun _ : ℂ => (n w₀ : ℂ)) (Metric.ball z r) w₀ :=
      continuousWithinAt_const
    have h1 : ContinuousWithinAt (fun w => ‖(n w : ℂ) - (n w₀ : ℂ)‖) (Metric.ball z r) w₀ :=
      ((hcast w₀ hw₀).sub hconst).norm
    exact h1.tendsto.eventually (Iio_mem_nhds (by simp))
  filter_upwards [hclose] with w hw
  have hlt : ‖((n w - n w₀ : ℤ) : ℂ)‖ < 1 := by push_cast; exact hw
  rw [Complex.norm_intCast, ← Int.cast_abs] at hlt
  have habs : |n w - n w₀| < (1 : ℤ) := by exact_mod_cast hlt
  rw [abs_lt] at habs
  omega

/-- Locally-constant principle for integer-valued functions on a ball.
If `f : ℂ → ℂ` is continuous on `Metric.ball z r` and satisfies
`f w = 2 * π * I * (n w : ℂ)` for `n : ℂ → ℤ`, then `n w = n z` for every
`w ∈ Metric.ball z r`. The ball is preconnected (convex), `n` is continuous by
`continuousOn_int_of_two_pi_I_mul_continuousOn`, and `IsPreconnected.constant` concludes. -/
theorem int_eq_const_on_ball_of_two_pi_I_mul_continuousOn
    {z : ℂ} {r : ℝ}
    (hr : 0 < r)
    {f : ℂ → ℂ}
    (hf : ContinuousOn f (Metric.ball z r))
    {n : ℂ → ℤ}
    (hfn : ∀ w ∈ Metric.ball z r,
              f w = 2 * Real.pi * Complex.I * (n w : ℂ)) :
    ∀ w ∈ Metric.ball z r, n w = n z := by
  intro w hw
  have hball_pc : IsPreconnected (Metric.ball z r) := (convex_ball z r).isPreconnected
  have hn_cts : ContinuousOn n (Metric.ball z r) :=
    continuousOn_int_of_two_pi_I_mul_continuousOn hr hf hfn
  exact hball_pc.constant hn_cts hw (Metric.mem_ball_self hr)

/-- For a closed $C^1$ path `γ` whose image stays at distance `> r` from `z`, and any
`w ∈ Metric.ball z r`, the log-derivative integral equals `2 * π * I * windingNumber γ w`.
This wraps `winding_integral_formula`: ball membership of `w` combined with `h_avoid`
gives `γ t ≠ w` for all `t ∈ [0, 1]` by the triangle inequality. -/
theorem integral_eq_two_pi_i_winding_on_ball
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (_hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z) :
    ∀ w ∈ Metric.ball z r,
      (∫ t in (0:ℝ)..1, deriv γ t / (γ t - w))
        = 2 * Real.pi * Complex.I * ((Complex.windingNumber γ w : ℤ) : ℂ) := by
  intro w hw
  have h_avoid_w : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ w := by
    intro t ht heq
    have hdist : r < dist (γ t) z := h_avoid t ht
    rw [heq] at hdist
    exact absurd (Metric.mem_ball.mp hw) (not_lt.mpr hdist.le)
  exact winding_integral_formula hγ h_avoid_w hclosed

/-- If the parametric integral `w ↦ ∫₀¹ deriv γ t / (γ t - w)` is continuous on
`Metric.ball z r` and `γ` avoids the ball, then `Complex.windingNumber γ` is constant on
the ball. Combines `integral_eq_two_pi_i_winding_on_ball` with the discrete-image-on-
connected-set principle `int_eq_const_on_ball_of_two_pi_I_mul_continuousOn`. -/
theorem windingNumber_eq_const_on_ball_of_continuousOn_integral
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z)
    (h_cts : ContinuousOn (fun w => ∫ t in (0 : ℝ)..1, deriv γ t / (γ t - w))
              (Metric.ball z r)) :
    ∀ w ∈ Metric.ball z r, Complex.windingNumber γ w = Complex.windingNumber γ z := by
  have h_eq := integral_eq_two_pi_i_winding_on_ball hγ hclosed hr h_avoid
  exact int_eq_const_on_ball_of_two_pi_I_mul_continuousOn hr h_cts h_eq

/-- If `F : ℂ → ℝ → ℂ` is jointly continuous on `Metric.closedBall w₀ r ×ˢ Set.Icc a b`,
then `w ↦ ∫ t in a..b, F w t` is continuous at `w₀`. The proof applies
`intervalIntegral.continuousAt_of_dominated_interval` with a constant bound from
compactness of `Metric.closedBall w₀ r ×ˢ Set.Icc a b`. -/
theorem continuousAt_intervalIntegral_of_continuousOn_closedBall
    {a b : ℝ} {F : ℂ → ℝ → ℂ} {w₀ : ℂ} {r : ℝ}
    (hr : 0 < r) (hab : a ≤ b)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
            (Metric.closedBall w₀ r ×ˢ Set.Icc a b)) :
    ContinuousAt (fun w => ∫ t in a..b, F w t) w₀ := by
  have hcpt : IsCompact (Metric.closedBall w₀ r ×ˢ Set.Icc a b) :=
    (isCompact_closedBall w₀ r).prod isCompact_Icc
  obtain ⟨M, hM⟩ := hcpt.exists_bound_of_continuousOn hF
  have uIoc_sub : Set.uIoc a b ⊆ Set.Icc a b := by
    rw [Set.uIoc_of_le hab]; exact Set.Ioc_subset_Icc_self
  apply intervalIntegral.continuousAt_of_dominated_interval (bound := fun _ => M)
  · filter_upwards [Metric.closedBall_mem_nhds w₀ hr] with w hw
    apply ContinuousOn.aestronglyMeasurable _ measurableSet_uIoc
    exact (hF.comp (continuousOn_const.prodMk continuousOn_id)
        (fun t ht => ⟨hw, ht⟩)).mono uIoc_sub
  · filter_upwards [Metric.closedBall_mem_nhds w₀ hr] with w hw
    filter_upwards using fun t ht => hM ⟨w, t⟩ ⟨hw, uIoc_sub ht⟩
  · exact intervalIntegrable_const
  · filter_upwards using fun t ht => by
      apply ContinuousOn.continuousAt _ (Metric.closedBall_mem_nhds w₀ hr)
      exact hF.comp (continuousOn_id.prodMk continuousOn_const)
        (fun w hw => ⟨hw, uIoc_sub ht⟩)

/-- If `F : ℂ → ℝ → ℂ` is jointly continuous on `U ×ˢ Set.Icc a b` for an open set `U`
and `a ≤ b`, then `w ↦ ∫ t in a..b, F w t` is continuous on `U`. For each `w₀ ∈ U` the
proof shrinks to a closed half-ball inside `U` and applies
`continuousAt_intervalIntegral_of_continuousOn_closedBall`. -/
theorem continuousOn_intervalIntegral_of_continuousOn_prod
    {U : Set ℂ} {a b : ℝ} {F : ℂ → ℝ → ℂ}
    (hU : IsOpen U) (hab : a ≤ b)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2) (U ×ˢ Set.Icc a b)) :
    ContinuousOn (fun w => ∫ t in a..b, F w t) U := by
  intro w₀ hw₀
  obtain ⟨r, hr, hball⟩ := Metric.isOpen_iff.mp hU w₀ hw₀
  have hr2 : (0 : ℝ) < r / 2 := by linarith
  have hsubset : Metric.closedBall w₀ (r/2) ⊆ U :=
    (Metric.closedBall_subset_ball (by linarith)).trans hball
  have hF' : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
      (Metric.closedBall w₀ (r/2) ×ˢ Set.Icc a b) :=
    hF.mono (Set.prod_mono hsubset Set.Subset.rfl)
  have h_at := continuousAt_intervalIntegral_of_continuousOn_closedBall hr2 hab hF'
  exact h_at.continuousWithinAt

/-- Specialisation of `continuousOn_intervalIntegral_of_continuousOn_prod` to the unit
interval: if `F` is jointly continuous on `Metric.ball z r ×ˢ Set.Icc 0 1`, then
`w ↦ ∫₀¹ F w t` is continuous on `Metric.ball z r`. -/
theorem continuousOn_intervalIntegral_ball_of_continuousOn_prod
    {z : ℂ} {r : ℝ} {F : ℂ → ℝ → ℂ}
    (_hr : 0 < r)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
            (Metric.ball z r ×ˢ Set.Icc 0 1)) :
    ContinuousOn (fun w => ∫ t in (0:ℝ)..1, F w t) (Metric.ball z r) := by
  exact continuousOn_intervalIntegral_of_continuousOn_prod
    (U := Metric.ball z r) (a := 0) (b := 1) (F := F)
    Metric.isOpen_ball zero_le_one hF

/-- The parametric integral `w ↦ ∫₀¹ derivWithin γ (Set.Icc 0 1) t / (γ t - w)` is
continuous on `Metric.ball z r` when `γ` is $C^1$ on `[0, 1]` and avoids the ball.
The joint continuity of the integrand follows from `integrand_joint_continuous_on_ball_icc`;
the bridge to parametric-integral continuity uses
`continuousOn_intervalIntegral_ball_of_continuousOn_prod`. -/
theorem continuousOn_derivWithin_div_intervalIntegral_ball
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z) :
    ContinuousOn
      (fun w => ∫ t in (0:ℝ)..1, derivWithin γ (Set.Icc 0 1) t / (γ t - w))
      (Metric.ball z r) := by
  have h_joint := integrand_joint_continuous_on_ball_icc hγ hr h_avoid
  exact continuousOn_intervalIntegral_ball_of_continuousOn_prod hr h_joint

/-- The parametric integral `w ↦ ∫₀¹ deriv γ t / (γ t - w)` is continuous on
`Metric.ball z r`. The proof swaps `deriv γ` for `derivWithin γ (Set.Icc 0 1)` almost
everywhere (they differ only at the endpoints), invokes
`continuousOn_derivWithin_div_intervalIntegral_ball`, then transports via `ContinuousOn.congr`. -/
theorem parametric_winding_integral_continuous_on_ball
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z) :
    ContinuousOn (fun w => ∫ t in (0:ℝ)..1, deriv γ t / (γ t - w))
      (Metric.ball z r) := by
  have h_eq := intervalIntegral_deriv_eq_derivWithin_div hγ hr h_avoid
  have h_cont := continuousOn_derivWithin_div_intervalIntegral_ball hγ hr h_avoid
  exact h_cont.congr (fun w hw => h_eq w hw)

/-- **Locally-constant winding number**: for a closed $C^1$ path `γ` whose image avoids
`Metric.ball z r`, `Complex.windingNumber γ w` is constant for `w ∈ Metric.ball z r`.
Continuity of the log-derivative integral on the ball follows from
`parametric_winding_integral_continuous_on_ball`; the discrete-image-on-connected-set
principle `windingNumber_eq_const_on_ball_of_continuousOn_integral` then concludes. -/
theorem winding_const_on_open_ball_off_image
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z) :
    ∀ w ∈ Metric.ball z r, Complex.windingNumber γ w = Complex.windingNumber γ z := by
  have h_cts := parametric_winding_integral_continuous_on_ball hγ hr h_avoid
  exact windingNumber_eq_const_on_ball_of_continuousOn_integral hγ hclosed hr h_avoid h_cts

end Library.Analysis.ResidueTheorem.WindingNumberFormula
