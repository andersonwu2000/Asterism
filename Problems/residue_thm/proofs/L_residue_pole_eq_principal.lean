import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10298

namespace Problems.residue_thm

-- residue_pole_eq_principal: residue of principal part equals residue of f at each pole,
-- using s10298 (radius independence) + Cauchy's theorem for the holomorphic remainder h a.
set_option linter.unusedVariables false in
set_option linter.style.multiGoal false in
theorem residue_pole_eq_principal
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (P : ℂ → ℂ → ℂ) (R : ℂ → ℝ) (h : ℂ → ℂ → ℂ)
    (hper : ∀ a ∈ T,
      0 < R a ∧
      Metric.ball a (R a) ⊆ U ∧
      (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a (R a)) ∧
      AnalyticOn ℂ (P a) (Set.univ \ {a}) ∧
      Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ (h a) (Metric.ball a (R a)) ∧
      (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z)) :
    ∀ a ∈ T, Complex.residue (P a) a = Complex.residue f a := by
  intro a ha
  obtain ⟨hR, hball, hdisjoint, hP, htend, hh, heq⟩ := hper a ha
  -- f is analytic on ball a (R a) \ {a}, using hf.mono
  have hsub : Metric.ball a (R a) \ {a} ⊆ U \ ↑T := by
    intro z ⟨hzball, hzne⟩
    refine ⟨hball hzball, ?_⟩
    simp only [Finset.mem_coe]
    intro hzT
    exact absurd hzball (hdisjoint z hzT (Set.mem_singleton_iff.not.mp hzne))
  have hfball : AnalyticOn ℂ f (Metric.ball a (R a) \ {a}) := hf.mono hsub
  -- P a is analytic on ball a (R a) \ {a}
  have hPball : AnalyticOn ℂ (P a) (Metric.ball a (R a) \ {a}) :=
    hP.mono (Set.diff_subset_diff_left (Set.subset_univ _))
  -- Conditions for Complex.residue
  have hPcond : ∃ r : ℝ, 0 < r ∧ AnalyticOn ℂ (P a) (Metric.ball a r \ {a}) :=
    ⟨R a, hR, hPball⟩
  have hfcond : ∃ r : ℝ, 0 < r ∧ AnalyticOn ℂ f (Metric.ball a r \ {a}) :=
    ⟨R a, hR, hfball⟩
  simp only [Complex.residue, dif_pos hPcond, dif_pos hfcond]
  congr 1
  -- rP = Classical.choose hPcond, rf = Classical.choose hfcond
  set rP := Classical.choose hPcond
  set rf := Classical.choose hfcond
  obtain ⟨hrP_pos, hPanal⟩ := Classical.choose_spec hPcond
  obtain ⟨hrf_pos, hfanal⟩ := Classical.choose_spec hfcond
  -- Common small radius
  set ε := min (rP / 4) (min (rf / 4) (R a / 4))
  have hε_pos : 0 < ε := by
    apply lt_min; linarith; apply lt_min <;> linarith
  have hε_le_rP2 : ε ≤ rP / 2 := (min_le_left _ _).trans (by linarith)
  have hε_lt_rP : ε < rP := hε_le_rP2.trans_lt (by linarith)
  have hε_le_rf2 : ε ≤ rf / 2 := ((min_le_right _ _).trans (min_le_left _ _)).trans (by linarith)
  have hε_lt_rf : ε < rf := hε_le_rf2.trans_lt (by linarith)
  have hε_lt_Ra : ε < R a := ((min_le_right _ _).trans (min_le_right _ _)).trans_lt (by linarith)
  -- Radius independence for P a: ∮ C(a, rP/2), P a z = ∮ C(a, ε), P a z
  have hP_rad : (∮ z in C(a, rP / 2), P a z) = ∮ z in C(a, ε), P a z :=
    (s10298 hPanal hε_pos hε_le_rP2 (by linarith)).symm
  -- Radius independence for f: ∮ C(a, rf/2), f z = ∮ C(a, ε), f z
  have hf_rad : (∮ z in C(a, rf / 2), f z) = ∮ z in C(a, ε), f z :=
    (s10298 hfanal hε_pos hε_le_rf2 (by linarith)).symm
  -- Sphere a ε ⊆ ball a (R a) \ {a}
  have hsphere_sub : Metric.sphere a ε ⊆ Metric.ball a (R a) \ {a} := by
    intro z hz
    rw [Metric.mem_sphere] at hz
    exact ⟨Metric.mem_ball.mpr (by linarith),
           Set.mem_singleton_iff.not.mpr (fun h => by simp [h, dist_self] at hz; linarith)⟩
  -- CircleIntegrable instances
  have hh_int : CircleIntegrable (h a) a ε :=
    (hh.continuousOn.mono (hsphere_sub.trans (Set.diff_subset))).circleIntegrable hε_pos.le
  have hP_int : CircleIntegrable (P a) a ε :=
    (hPball.continuousOn.mono hsphere_sub).circleIntegrable hε_pos.le
  -- Cauchy: ∮ C(a, ε), h a z = 0
  have hh_zero : (∮ z in C(a, ε), h a z) = 0 := by
    apply DiffContOnCl.circleIntegral_eq_zero hε_pos.le
    exact DiffContOnCl.mk_ball
      (hh.differentiableOn.mono (Metric.ball_subset_ball hε_lt_Ra.le))
      (hh.continuousOn.mono (Metric.closedBall_subset_ball hε_lt_Ra))
  -- f = h a + P a on the circle
  have hfε_eq : (∮ z in C(a, ε), f z) = ∮ z in C(a, ε), P a z := by
    have hcongr : Set.EqOn f (fun z => h a z + P a z) (Metric.sphere a ε) :=
      fun z hz => heq z (hsphere_sub hz)
    rw [circleIntegral.integral_congr hε_pos.le hcongr,
        circleIntegral.integral_add hh_int hP_int, hh_zero, zero_add]
  rw [hP_rad, hf_rad, hfε_eq]

end Problems.residue_thm

