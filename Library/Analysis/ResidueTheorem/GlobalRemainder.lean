import Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
import Library.Analysis.ResidueTheorem.PoleGluing
import Library.Analysis.ResidueTheorem.PrincipalPartExtraction

/-!
# Global Remainder for the Residue Theorem

This file assembles the principal-part decomposition and residue-equality results
needed for the global form of the Residue Theorem.

Given a meromorphic function `f` on an open set `U ⊆ ℂ` with a finite pole set `T`,
we extract, for each pole `a ∈ T`, an isolating ball and a Laurent-type decomposition
`f = h_a + P_a` on that punctured ball (holomorphic part plus principal part).
`global_remainder_glue` combines these local data and produces a globally analytic
function `g : ℂ → ℂ` on `U` satisfying `f = g + ∑ a ∈ T, P a` on `U \ T`, together
with the residue equality `Complex.residue (P a) a = Complex.residue f a` at each pole.

## Main statements

- `residue_pole_eq_principal`: the residue of the principal part `P a` equals the
  residue of `f` at each pole `a ∈ T`.
- `isolating_radius_in_open_finset`: for each pole there exists a radius isolating it
  from all other poles.
- `exists_principal_part_add_analyticOn`: Laurent decomposition of `f` on a punctured
  ball around an isolated singularity.
- `per_pole_principal_part_data`: Skolemised collection of per-pole decomposition data.
- `global_remainder_glue`: the main combinator assembling analytic gluing and residue
  equality.
-/

open Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
open Library.Analysis.ResidueTheorem.PoleGluing
open Library.Analysis.ResidueTheorem.PrincipalPartExtraction

namespace Library.Analysis.ResidueTheorem.GlobalRemainder

/-- The residue of the principal part `P a` at a pole equals the residue of `f` there.

Given per-pole data `(P, R, h)` where `f = h a + P a` on a punctured ball of radius `R a`
around each `a ∈ T`, this follows from radius-independence of the circle integral
(`circle_integral_radius_indep_on_punctured_ball`) and Cauchy's theorem for the holomorphic
part `h a`. -/
theorem residue_pole_eq_principal
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (_hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
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
  obtain ⟨hR, hball, hdisjoint, hP, _htend, hh, heq⟩ := hper a ha
  have hsub : Metric.ball a (R a) \ {a} ⊆ U \ ↑T := by
    intro z ⟨hzball, hzne⟩
    refine ⟨hball hzball, ?_⟩
    simp only [Finset.mem_coe]
    intro hzT
    exact absurd hzball (hdisjoint z hzT (Set.mem_singleton_iff.not.mp hzne))
  have hfball : AnalyticOn ℂ f (Metric.ball a (R a) \ {a}) := hf.mono hsub
  have hPball : AnalyticOn ℂ (P a) (Metric.ball a (R a) \ {a}) :=
    hP.mono (Set.diff_subset_diff_left (Set.subset_univ _))
  have hPcond : ∃ r : ℝ, 0 < r ∧ AnalyticOn ℂ (P a) (Metric.ball a r \ {a}) :=
    ⟨R a, hR, hPball⟩
  have hfcond : ∃ r : ℝ, 0 < r ∧ AnalyticOn ℂ f (Metric.ball a r \ {a}) :=
    ⟨R a, hR, hfball⟩
  simp only [Complex.residue, dif_pos hPcond, dif_pos hfcond]
  congr 1
  set rP := Classical.choose hPcond
  set rf := Classical.choose hfcond
  obtain ⟨hrP_pos, hPanal⟩ := Classical.choose_spec hPcond
  obtain ⟨hrf_pos, hfanal⟩ := Classical.choose_spec hfcond
  set ε := min (rP / 4) (min (rf / 4) (R a / 4))
  have hε_pos : 0 < ε := by
    apply lt_min
    · linarith
    · apply lt_min <;> linarith
  have hε_le_rP2 : ε ≤ rP / 2 := (min_le_left _ _).trans (by linarith)
  have hε_le_rf2 : ε ≤ rf / 2 :=
    ((min_le_right _ _).trans (min_le_left _ _)).trans (by linarith)
  have hε_lt_Ra : ε < R a :=
    ((min_le_right _ _).trans (min_le_right _ _)).trans_lt (by linarith)
  have hP_rad : (∮ z in C(a, rP / 2), P a z) = ∮ z in C(a, ε), P a z :=
    (circle_integral_radius_indep_on_punctured_ball hPanal hε_pos hε_le_rP2 (by linarith)).symm
  have hf_rad : (∮ z in C(a, rf / 2), f z) = ∮ z in C(a, ε), f z :=
    (circle_integral_radius_indep_on_punctured_ball hfanal hε_pos hε_le_rf2 (by linarith)).symm
  have hsphere_sub : Metric.sphere a ε ⊆ Metric.ball a (R a) \ {a} := by
    intro z hz
    rw [Metric.mem_sphere] at hz
    exact ⟨Metric.mem_ball.mpr (by linarith),
           Set.mem_singleton_iff.not.mpr (fun h => by simp [h, dist_self] at hz; linarith)⟩
  have hh_int : CircleIntegrable (h a) a ε :=
    (hh.continuousOn.mono (hsphere_sub.trans Set.diff_subset)).circleIntegrable hε_pos.le
  have hP_int : CircleIntegrable (P a) a ε :=
    (hPball.continuousOn.mono hsphere_sub).circleIntegrable hε_pos.le
  have hh_zero : (∮ z in C(a, ε), h a z) = 0 := by
    apply DiffContOnCl.circleIntegral_eq_zero hε_pos.le
    exact DiffContOnCl.mk_ball
      (hh.differentiableOn.mono (Metric.ball_subset_ball hε_lt_Ra.le))
      (hh.continuousOn.mono (Metric.closedBall_subset_ball hε_lt_Ra))
  have hfε_eq : (∮ z in C(a, ε), f z) = ∮ z in C(a, ε), P a z := by
    have hcongr : Set.EqOn f (fun z => h a z + P a z) (Metric.sphere a ε) :=
      fun z hz => heq z (hsphere_sub hz)
    rw [circleIntegral.integral_congr hε_pos.le hcongr,
        circleIntegral.integral_add hh_int hP_int, hh_zero, zero_add]
  rw [hP_rad, hf_rad, hfε_eq]

/-- For each pole `a ∈ T`, there exists a radius $r > 0$ such that `Metric.ball a r ⊆ U`
and no other pole `b ∈ T` lies in that ball.

This is a purely topological fact: `U` is open (giving the first ball), and `T` is finite
(so the minimum distance to other poles is positive). -/
theorem isolating_radius_in_open_finset
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (_hf : AnalyticOn ℂ f (U \ ↑T)) :
    ∀ a ∈ T, ∃ r : ℝ, 0 < r ∧ Metric.ball a r ⊆ U ∧
      ∀ b ∈ T, b ≠ a → b ∉ Metric.ball a r := by
  intro a haT
  have haU : a ∈ U := hT a haT
  obtain ⟨r₁, hr₁pos, hr₁ball⟩ := Metric.isOpen_iff.mp hU a haU
  rcases Finset.eq_empty_or_nonempty (T.erase a) with hS | hS
  · exact ⟨r₁, hr₁pos, hr₁ball, fun b hbT hba => by
      have : b ∈ T.erase a := Finset.mem_erase.mpr ⟨hba, hbT⟩
      simp [hS] at this⟩
  · have hpos : ∀ b ∈ T.erase a, 0 < dist a b := fun b hb =>
      dist_pos.mpr (Ne.symm (Finset.mem_erase.mp hb).1)
    set r₂ := (T.erase a).inf' hS (dist a)
    have hr₂pos : 0 < r₂ := by
      rw [Finset.lt_inf'_iff]; exact hpos
    refine ⟨min r₁ (r₂ / 2), lt_min hr₁pos (half_pos hr₂pos),
      (Metric.ball_subset_ball (min_le_left _ _)).trans hr₁ball, ?_⟩
    intro b hbT hba hball
    have hbS : b ∈ T.erase a := Finset.mem_erase.mpr ⟨hba, hbT⟩
    have hle : r₂ ≤ dist a b := Finset.inf'_le _ hbS
    rw [Metric.mem_ball, dist_comm] at hball
    linarith [min_le_right r₁ (r₂ / 2)]

/-- Laurent decomposition of `f` near an isolated singularity.

Given `f` analytic on the punctured ball `Metric.ball z₀ R \ {z₀}`, produces holomorphic
`g : ℂ → ℂ` on the full ball and a principal part `P : ℂ → ℂ` (analytic on `ℂ \ {z₀}`,
vanishing at infinity) such that `f z = g z + P z` for all `z` in the punctured ball.
Wraps `principal_part_extraction_at_singularity`. -/
theorem exists_principal_part_add_analyticOn
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (P g : ℂ → ℂ),
      AnalyticOn ℂ P (Set.univ \ {z₀}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ g (Metric.ball z₀ R) ∧
      ∀ z ∈ Metric.ball z₀ R \ {z₀}, f z = g z + P z := by
  exact principal_part_extraction_at_singularity hR hf

/-- Pointwise existence of principal-part decomposition data for each `a : ℂ`.

For `a ∈ T`, produces an isolating radius `r`, principal part `P_a`, and holomorphic
remainder `h_a` satisfying all the conditions of `exists_principal_part_add_analyticOn`.
For `a ∉ T` the implication is vacuously true; dummy witnesses are supplied.
This is the Skolemised pointwise version, later packaged uniformly by
`per_pole_principal_part_data`. -/
theorem pointwise_pole_principal_data
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T)) :
    ∀ a : ℂ, ∃ (r : ℝ) (P_a h_a : ℂ → ℂ),
      a ∈ T →
      (0 < r ∧
       Metric.ball a r ⊆ U ∧
       (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a r) ∧
       AnalyticOn ℂ P_a (Set.univ \ {a}) ∧
       Filter.Tendsto P_a (Filter.cocompact ℂ) (nhds 0) ∧
       AnalyticOn ℂ h_a (Metric.ball a r) ∧
       (∀ z ∈ Metric.ball a r \ {a}, f z = h_a z + P_a z)) := by
  intro a
  by_cases ha : a ∈ T
  · obtain ⟨r, hr_pos, hr_subU, hr_iso⟩ :=
      isolating_radius_in_open_finset hU hT hf a ha
    have hf' : AnalyticOn ℂ f (Metric.ball a r \ {a}) := by
      apply hf.mono
      rintro z ⟨hzball, hz_ne⟩
      refine ⟨hr_subU hzball, ?_⟩
      intro hzT
      have hzne_a : z ≠ a := fun h => hz_ne (Set.mem_singleton_iff.mpr h)
      exact hr_iso z hzT hzne_a hzball
    obtain ⟨P, g, hP_an, hP_t, hg_an, hsum⟩ :=
      exists_principal_part_add_analyticOn hr_pos hf'
    exact ⟨r, P, g, fun _ => ⟨hr_pos, hr_subU, hr_iso, hP_an, hP_t, hg_an, hsum⟩⟩
  · exact ⟨1, 0, 0, fun haT => absurd haT ha⟩

/-- Skolemised collection of per-pole decomposition data for all poles simultaneously.

Applies `pointwise_pole_principal_data` via `classical` Skolemisation to produce
functions `P : ℂ → ℂ → ℂ`, `R : ℂ → ℝ`, and `h : ℂ → ℂ → ℂ` such that for every
`a ∈ T` the triple `(P a, R a, h a)` satisfies the full Laurent decomposition
conditions at `a`. -/
theorem per_pole_principal_part_data
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ (P : ℂ → ℂ → ℂ) (R : ℂ → ℝ) (h : ℂ → ℂ → ℂ),
      ∀ a ∈ T,
        0 < R a ∧
        Metric.ball a (R a) ⊆ U ∧
        (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a (R a)) ∧
        AnalyticOn ℂ (P a) (Set.univ \ {a}) ∧
        Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) ∧
        AnalyticOn ℂ (h a) (Metric.ball a (R a)) ∧
        (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z) := by
  classical
  choose R P h hcond using pointwise_pole_principal_data hU hT hf
  exact ⟨P, R, h, hcond⟩

/-- **Global remainder glue**: combines analytic gluing and residue equality for the
Residue Theorem.

Given per-pole data `(P, R, h)` certifying the Laurent decomposition at each `a ∈ T`, this
produces an analytic function `g : ℂ → ℂ` on `U` such that:
- `f z = g z + ∑ a ∈ T, P a z` for all `z ∈ U \ T`, and
- `Complex.residue (P a) a = Complex.residue f a` for each `a ∈ T`.
The analytic gluing is provided by `exists_analyticOn_eq_add_sum` and the residue equality
by `residue_pole_eq_principal`. -/
theorem global_remainder_glue
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
    ∃ (g : ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) ∧
      (∀ a ∈ T, Complex.residue (P a) a = Complex.residue f a) := by
  have h_glue := exists_analyticOn_eq_add_sum hU hT hf hγ hmaps P R h hper
  have h_res := residue_pole_eq_principal hU hT hf hγ hmaps P R h hper
  obtain ⟨g, hg_anal, hg_pw⟩ := h_glue
  exact ⟨g, hg_anal, hg_pw, h_res⟩

end Library.Analysis.ResidueTheorem.GlobalRemainder
