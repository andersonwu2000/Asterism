import Mathlib
import Library.Analysis.ResidueTheorem.PathConnector

/-!
# Primitive Construction on the Punctured Plane

This file constructs a primitive (antiderivative) for a function `Q` analytic on
`ℂ \ {a}` from the hypothesis that every closed $C^1$ loop integral of `Q` vanishes.

## Main statements

- `primitive_on_punctured_plane_from_zero_loops`: if `Q` is analytic on `ℂ \ {a}` and
  every closed $C^1$ loop integral of `Q` is zero, then `Q` admits a primitive on
  `ℂ \ {a}`.

## Implementation notes

The core technique is the *straight-line segment trick*: for $z \neq a$ and
$\|h\| < \operatorname{dist}(z, a)$, the segment $\gamma_h(t) = z + th$ lies entirely in
`ℂ \ {a}`. Applying the path-integral identity to `γ_h` gives
$F(z+h) - F(z) = \int_0^1 Q(z+th) \cdot h \, dt$. Dominated convergence then shows
this quotient tends to $Q(z)$ as $h \to 0$, establishing `HasDerivAt F (Q z) z`.
-/

open Library.Analysis.ResidueTheorem.PathConnector

namespace Library.Analysis.ResidueTheorem.PrimitiveConstruction

/-- The segment integral $\int_0^1 Q(z + t \cdot 0) \, dt$ equals `Q z`,
since `t * 0 = 0` for all `t`. -/
theorem integral_segment_zero
    (Q : ℂ → ℂ) (z : ℂ) :
    (∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * 0)) = Q z := by norm_num

/-- For `z ≠ a` with `‖h‖ < dist z a`, every point on the segment
$t \mapsto z + th$ for $t \in [0, 1]$ avoids the pole `a`. -/
theorem segment_avoids_pole {a : ℂ} (z : ℂ) (_hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h : ℂ) (hh : ‖h‖ < dist z a) :
    ∀ t ∈ Set.Icc (0:ℝ) 1, z + (t:ℂ) * h ≠ a := by
  intro t ht heq
  have hlt : ‖(t : ℂ) * h‖ < dist z a :=
    calc ‖(t : ℂ) * h‖ = ‖(t : ℂ)‖ * ‖h‖ := norm_mul _ _
      _ ≤ 1 * ‖h‖ := by
          apply mul_le_mul_of_nonneg_right _ (norm_nonneg _)
          simp only [Complex.norm_real, Real.norm_eq_abs, abs_of_nonneg ht.1]
          exact ht.2
      _ = ‖h‖ := one_mul _
      _ < dist z a := hh
  have heq' : a - z = (t : ℂ) * h := by linear_combination -heq
  have hdist : dist z a = ‖(t : ℂ) * h‖ := by
    rw [dist_comm, dist_eq_norm, ← heq']
  linarith

/-- The derivative of the straight-line segment $s \mapsto z + sh$ equals `h`
at every real point `t`. -/
theorem segment_const_deriv (z h : ℂ) (t : ℝ) :
    deriv (fun s : ℝ => z + (s:ℂ) * h) t = h := by
  have hd : HasDerivAt (fun s : ℝ => z + (s : ℂ) * h) h t := by
    have h2 : HasDerivAt (fun s : ℝ => (s : ℂ) * h) (1 * h) t :=
      (Complex.ofRealCLM.hasDerivAt (x := t)).mul_const h
    simpa using h2.const_add z
  exact hd.deriv

/-- The straight-line segment $t \mapsto z + th$ is $C^1$ on $[0, 1]$. -/
theorem segment_contdiff (z h : ℂ) :
    ContDiffOn ℝ 1 (fun t : ℝ => z + (t:ℂ) * h) (Set.Icc 0 1) := by
  apply ContDiff.contDiffOn
  apply ContDiff.add contDiff_const
  have heq : (fun t : ℝ => (t : ℂ) * h) = fun t : ℝ => t • h := by
    ext t; simp [Algebra.smul_def]
  rw [heq]
  exact contDiff_id.smul_const h

/-- **Segment path-integral identity**: if `F` satisfies the path-integral equation
$F(\gamma(1)) - F(\gamma(0)) = \int_0^1 Q(\gamma(t))\,\gamma'(t)\,dt$ for every
$C^1$ path in `ℂ \ {a}`, then for every `z ≠ a` and `‖h‖ < dist z a`,
$$F(z + h) - F(z) = \int_0^1 Q(z + th) \cdot h \, dt.$$ -/
theorem segment_path_integral_identity
    {Q : ℂ → ℂ} {a : ℂ}
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    (F : ℂ → ℂ)
    (hF : ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h := by
  intro z hz h hh
  have h_C1 : ContDiffOn ℝ 1 (fun t : ℝ => z + (t:ℂ) * h) (Set.Icc 0 1) :=
    segment_contdiff z h
  have h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, z + (t:ℂ) * h ≠ a :=
    segment_avoids_pole z hz h hh
  have h_deriv : ∀ t : ℝ, deriv (fun s : ℝ => z + (s:ℂ) * h) t = h :=
    fun t => segment_const_deriv z h t
  have hpath := hF (fun t : ℝ => z + (t:ℂ) * h) h_C1 h_avoid
  have h0 : (fun t : ℝ => z + (t:ℂ) * h) 0 = z := by push_cast; ring
  have h1 : (fun t : ℝ => z + (t:ℂ) * h) 1 = z + h := by push_cast; ring
  rw [h0, h1] at hpath
  rw [hpath]
  refine intervalIntegral.integral_congr (fun t _ => ?_)
  simp [h_deriv]

/-- Almost everywhere (in `t`), the map `h ↦ Q (z + t * h)` is continuous at `h = 0`,
given that `Q` is continuous on the closed ball `Metric.closedBall z R`. -/
theorem ae_continuousAt_segment_integrand
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    ∀ᵐ t ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ),
      t ∈ Set.uIoc (0:ℝ) 1 → ContinuousAt (fun h : ℂ => Q (z + (t : ℂ) * h)) 0 := by
  apply Filter.Eventually.of_forall
  intro t _ht
  apply (hQ.continuousAt (Metric.closedBall_mem_nhds z hR)).comp_of_eq (by fun_prop)
  simp

/-- For `h` in a neighborhood of `0`, the integrand `t ↦ Q (z + t * h)` is
almost-everywhere strongly measurable on `[0, 1]`, given that `Q` is continuous on
`Metric.closedBall z R`. -/
theorem eventually_aeStronglyMeasurable_segment_integrand
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    ∀ᶠ h in nhds (0:ℂ),
      MeasureTheory.AEStronglyMeasurable (fun t : ℝ => Q (z + (t : ℂ) * h))
        (MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) 1)) := by
  apply Filter.Eventually.mono (Metric.ball_mem_nhds 0 hR)
  intro h hh
  rw [dist_zero_right] at hh
  apply ContinuousOn.aestronglyMeasurable _ measurableSet_uIoc
  apply hQ.comp
    ((continuous_const.add (Complex.continuous_ofReal.mul continuous_const)).continuousOn)
  intro t ht
  simp only [Pi.add_apply, Pi.mul_apply, Metric.mem_closedBall,
             Complex.dist_eq, add_sub_cancel_left]
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)] at ht
  rw [norm_mul, Complex.norm_real]
  calc |t| * ‖h‖ ≤ 1 * ‖h‖ := by
        apply mul_le_mul_of_nonneg_right _ (norm_nonneg _)
        rw [abs_of_pos ht.1]; exact ht.2
    _ = ‖h‖ := one_mul _
    _ ≤ R := hh.le

/-- There exists a uniform bound `M` such that, for all `h` near `0` and almost every
`t ∈ [0, 1]`, we have `‖Q (z + t * h)‖ ≤ M`. This is the dominating bound for
the dominated convergence theorem. -/
theorem exists_norm_bound_segment_integrand
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    ∃ M : ℝ, ∀ᶠ h in nhds (0:ℂ),
      ∀ᵐ t ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ),
        t ∈ Set.uIoc (0:ℝ) 1 → ‖Q (z + (t : ℂ) * h)‖ ≤ M := by
  obtain ⟨w₀, _, hmax⟩ := (isCompact_closedBall z R).exists_isMaxOn
    (Metric.nonempty_closedBall.mpr hR.le) hQ.norm
  refine ⟨‖Q w₀‖, ?_⟩
  filter_upwards [Metric.ball_mem_nhds (0 : ℂ) hR] with h hh
  apply MeasureTheory.ae_of_all
  intro t ht
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)] at ht
  have ht1 : ‖(t : ℂ)‖ ≤ 1 := by
    have heq : ‖(t : ℂ)‖ = |t| := RCLike.norm_ofReal t
    rw [heq, abs_of_nonneg ht.1.le]; exact ht.2
  apply hmax
  rw [Metric.mem_closedBall]
  calc dist (z + (t : ℂ) * h) z
      = ‖(t : ℂ) * h‖ := by rw [dist_comm]; simp [dist_eq_norm]
    _ ≤ ‖(t : ℂ)‖ * ‖h‖ := norm_mul_le _ _
    _ ≤ ‖h‖ := mul_le_of_le_one_left (norm_nonneg _) ht1
    _ ≤ R := by rw [← dist_zero_right]; exact (Metric.mem_ball.mp hh).le

/-- The parametric integral $h \mapsto \int_0^1 Q(z + th)\,dt$ is continuous at `h = 0`,
given that `Q` is continuous on `Metric.closedBall z R`. The proof applies the
dominated convergence theorem via `intervalIntegral.continuousAt_of_dominated_interval`. -/
theorem continuous_at_segment_integral_of_continuous_on_closed_ball
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    ContinuousAt (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h)) 0 := by
  have h_aemeas := eventually_aeStronglyMeasurable_segment_integrand Q z R hR hQ
  have h_bound := exists_norm_bound_segment_integrand Q z R hR hQ
  have h_cont := ae_continuousAt_segment_integrand Q z R hR hQ
  obtain ⟨M, hM⟩ := h_bound
  exact intervalIntegral.continuousAt_of_dominated_interval h_aemeas hM
    intervalIntegrable_const h_cont

/-- The segment average $h \mapsto \int_0^1 Q(z + th)\,dt$ tends to `Q z` as `h → 0`,
given that `Q` is continuous on `Metric.closedBall z R`. -/
theorem segment_avg_tendsto_of_continuous_on_closed_ball
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z)) := by
  have h_val := integral_segment_zero Q z
  have h_cont := continuous_at_segment_integral_of_continuous_on_closed_ball Q z R hR hQ
  rw [← h_val]
  exact h_cont

/-- If `Q` is continuous on `ℂ \ {a}` and `z ≠ a`, then `Q` is continuous on the closed
ball `Metric.closedBall z (dist z a / 2)`, which lies inside `ℂ \ {a}`. -/
theorem continuousOn_closedBall_of_punctured
    {Q : ℂ → ℂ} {a : ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont_on : ContinuousOn Q (Set.univ \ ({a} : Set ℂ))) :
    ContinuousOn Q (Metric.closedBall z (dist z a / 2)) := by
  apply h_cont_on.mono
  intro w hw
  simp only [Metric.mem_closedBall] at hw
  simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and]
  intro heq
  subst heq
  simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and] at hz
  have hdist : 0 < dist z w := dist_pos.mpr hz
  linarith [dist_comm z w]

/-- The segment average $h \mapsto \int_0^1 Q(z + th)\,dt$ tends to `Q z` as `h → 0`,
given that `Q` is continuous on the punctured plane `ℂ \ {a}` and `z ≠ a`. -/
theorem tendsto_segment_avg_of_punctured
    {Q : ℂ → ℂ} {a : ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont_on : ContinuousOn Q (Set.univ \ ({a} : Set ℂ))) :
    Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z)) := by
  have hzne : z ≠ a := fun h => hz.2 (Set.mem_singleton_iff.mpr h)
  have h_dist_pos : 0 < dist z a := dist_pos.mpr hzne
  have hR : (0 : ℝ) < dist z a / 2 := by linarith
  have h_ball_cont := continuousOn_closedBall_of_punctured z hz h_cont_on
  exact segment_avg_tendsto_of_continuous_on_closed_ball Q z (dist z a / 2) hR h_ball_cont

/-- If `F` satisfies the segment integral identity near `z` and the segment average
$\int_0^1 Q(z + th)\,dt$ tends to `Q z`, then `F` has derivative `Q z` at `z`. -/
theorem hasDerivAt_of_tendsto_segment_avg
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ} (z : ℂ)
    (hzne : z ≠ a)
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h)
    (h_avg : Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z))) :
    HasDerivAt F (Q z) z := by
  rw [hasDerivAt_iff_tendsto_slope_zero]
  have hdist : 0 < dist z a := dist_pos.mpr hzne
  apply (h_avg.mono_left nhdsWithin_le_nhds).congr'
  filter_upwards [nhdsWithin_le_nhds (Metric.ball_mem_nhds (0 : ℂ) hdist),
                  self_mem_nhdsWithin] with h hlt hne
  simp only [Set.mem_compl_iff, Set.mem_singleton_iff] at hne
  simp only [Metric.mem_ball, dist_zero_right] at hlt
  simp only [smul_eq_mul]
  have hh := h_seg h hlt
  rw [hh]
  simp_rw [mul_comm (Q _) h]
  have hint : ∫ t in (0:ℝ)..1, h * Q (z + (t:ℂ) * h) =
              h * ∫ t in (0:ℝ)..1, Q (z + (t:ℂ) * h) :=
    intervalIntegral.integral_const_mul h _
  rw [hint, ← mul_assoc, inv_mul_cancel₀ hne, one_mul]

/-- If `Q` is continuous on `ℂ \ {a}`, `z ≠ a`, and `F` satisfies the segment integral
identity $F(z+h) - F(z) = \int_0^1 Q(z+th) \cdot h \, dt$ for small `h`, then `F` has
derivative `Q z` at `z`. -/
theorem hasDerivAt_of_continuousOn_segment_identity
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont_on : ContinuousOn Q (Set.univ \ ({a} : Set ℂ)))
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h) :
    HasDerivAt F (Q z) z := by
  have hzne : z ≠ a := by intro h; exact hz.2 (Set.mem_singleton_iff.mpr h)
  have h_avg := tendsto_segment_avg_of_punctured z hz h_cont_on
  exact hasDerivAt_of_tendsto_segment_avg z hzne h_seg h_avg

/-- If `Q` is analytic on `ℂ \ {a}` and `F` satisfies the segment integral identity on
`ℂ \ {a}`, then `F` has derivative `Q z` at every `z ∈ ℂ \ {a}`. -/
theorem hasDerivAt_of_segment_identity
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    (F : ℂ → ℂ)
    (_hF : ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t)
    (h_segment : ∀ z ∈ Set.univ \ ({a} : Set ℂ), ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), HasDerivAt F (Q z) z := by
  intro z hz
  have h_cont_on : ContinuousOn Q (Set.univ \ ({a} : Set ℂ)) :=
    (hQ_an.continuousOn)
  have h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h :=
    h_segment z hz
  exact hasDerivAt_of_continuousOn_segment_identity z hz h_cont_on h_seg

/-- If `Q` is analytic on `ℂ \ {a}` and `F` has the path-integral property for every
$C^1$ path in `ℂ \ {a}`, then `F` has derivative `Q z` at every `z ∈ ℂ \ {a}`.
This combines the segment path-integral identity with analyticity. -/
theorem hasDerivAt_of_path_primitive
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    (F : ℂ → ℂ)
    (hF : ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), HasDerivAt F (Q z) z := by
  have h_seg := segment_path_integral_identity hQ_an h_loops F hF
  exact hasDerivAt_of_segment_identity hQ_an h_loops F hF h_seg

/-- **Morera-style primitive construction**: if `Q` is analytic on `ℂ \ {a}` and every
closed $C^1$ loop integral of `Q` in `ℂ \ {a}` vanishes, then `Q` has a primitive `F`
on `ℂ \ {a}`, i.e., there exists `F : ℂ → ℂ` with `HasDerivAt F (Q z) z` for all
`z ∈ ℂ \ {a}`. -/
theorem primitive_on_punctured_plane_from_zero_loops
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0) :
    ∃ F : ℂ → ℂ, ∀ z ∈ Set.univ \ ({a} : Set ℂ),
      HasDerivAt F (Q z) z := by
  have h_pathF := path_primitive_exists_from_closed_loops hQ_an h_loops
  obtain ⟨F, hF⟩ := h_pathF
  exact ⟨F, hasDerivAt_of_path_primitive hQ_an h_loops F hF⟩

end Library.Analysis.ResidueTheorem.PrimitiveConstruction
