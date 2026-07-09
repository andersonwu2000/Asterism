import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Calculus.ContDiff.Deriv
import Mathlib.Analysis.Calculus.ContDiff.Operations
import Mathlib.MeasureTheory.Integral.IntervalIntegral.FundThmCalculus
import Mathlib.Order.BourbakiWitt

/-!
# Smoothness of the piecewise-concatenation integral primitive

This file establishes that the integral primitive arising from the flat-endpoint
concatenation of two $C^1$ paths is itself $C^1$ on $[0, 1]$.

Given two $C^1$ paths `α'`, `β' : ℝ → ℂ` on `[0, 1]` whose derivatives vanish at the
join point (`derivWithin α' (Icc 0 1) 1 = 0` and `derivWithin β' (Icc 0 1) 0 = 0`), the
piecewise velocity
$$s \mapsto \begin{cases} 2\,\alpha''(2s) & s \le 1/2 \\ 2\,\beta''(2s-1) & s > 1/2 \end{cases}$$
is continuous on $[0, 1]$, and the associated integral primitive is $C^1$.

## Main statements

- `piecewise_velocity_continuous_on_icc`: the piecewise velocity is continuous on `Icc 0 1`.
- `c1_const_add_indefinite_integral`: a constant plus the indefinite integral of a continuous
  function is $C^1$ on `Icc 0 1`.
- `flat_concat_ftc_smooth`: the piecewise-FTC primitive is $C^1$ on `Icc 0 1`.
- `contDiffOn_piecewiseConcat_integral`: the full version accepting avoidance hypotheses.
-/

namespace Library.Analysis.ResidueTheorem.PathConcatSmoothness

/-- The left branch of the piecewise velocity, $s \mapsto 2\,\alpha''(2s)$, is continuous
on $[0, 1/2]$ whenever `α'` is $C^1$ on $[0, 1]$. -/
theorem left_branch_velocity_continuous
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (_hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContinuousOn (fun s : ℝ => 2 * derivWithin α' (Set.Icc 0 1) (2 * s))
      (Set.Icc 0 ((1 : ℝ) / 2)) := by
  have hcont : ContinuousOn (derivWithin α' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hα'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hmaps : Set.MapsTo (fun s : ℝ => 2 * s) (Set.Icc 0 (1 / 2)) (Set.Icc 0 1) := by
    intro s hs
    constructor
    · linarith [hs.1]
    · linarith [hs.2]
  exact continuousOn_const.mul
    (hcont.comp ((continuous_const.mul continuous_id).continuousOn) hmaps)

/-- The right branch of the piecewise velocity, $s \mapsto 2\,\beta''(2s-1)$, is continuous
on $[1/2, 1]$ whenever `β'` is $C^1$ on $[0, 1]$. -/
theorem right_branch_velocity_continuous
    {α' β' : ℝ → ℂ}
    (_hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (_hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContinuousOn (fun s : ℝ => 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      (Set.Icc ((1 : ℝ) / 2) 1) := by
  have hderiv : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one (by norm_num)
  have hmap : ContinuousOn (fun s : ℝ => 2 * s - 1) (Set.Icc ((1 : ℝ) / 2) 1) :=
    ((continuous_const.mul continuous_id).sub continuous_const).continuousOn
  have hmapsTo : Set.MapsTo (fun s : ℝ => 2 * s - 1) (Set.Icc ((1 : ℝ) / 2) 1) (Set.Icc 0 1) := by
    intro s hs
    simp only [Set.mem_Icc] at hs ⊢
    constructor <;> linarith [hs.1, hs.2]
  exact continuousOn_const.mul (hderiv.comp hmap hmapsTo)

/-- The piecewise velocity
$$s \mapsto \begin{cases} 2\,\alpha''(2s) & s \le 1/2 \\ 2\,\beta''(2s-1) & s > 1/2 \end{cases}$$
is continuous on $[0, 1]$, provided `α'` and `β'` are $C^1$ on $[0, 1]$ with
`derivWithin α' (Icc 0 1) 1 = 0` and `derivWithin β' (Icc 0 1) 0 = 0`.

The continuity is established by gluing the left and right branches via `ContinuousOn.if`;
junction agreement at $s = 1/2$ follows from the flat-endpoint hypotheses. -/
theorem piecewise_velocity_continuous_on_icc
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContinuousOn
      (fun s : ℝ => if s ≤ (1 : ℝ) / 2
        then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      (Set.Icc 0 1) := by
  have h_left_raw := left_branch_velocity_continuous hα' hβ' hα'_deriv hβ'_deriv
  have h_right_raw := right_branch_velocity_continuous hα' hβ' hα'_deriv hβ'_deriv
  have h_left : ContinuousOn (fun s : ℝ => 2 * derivWithin α' (Set.Icc 0 1) (2 * s))
      (Set.Icc 0 1 ∩ closure {a : ℝ | a ≤ (1 : ℝ) / 2}) :=
    h_left_raw.mono fun x hx => ⟨hx.1.1, isClosed_Iic.closure_subset hx.2⟩
  have h_right : ContinuousOn (fun s : ℝ => 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      (Set.Icc 0 1 ∩ closure {a : ℝ | ¬ a ≤ (1 : ℝ) / 2}) := by
    apply h_right_raw.mono
    intro x hx
    have hmem : x ∈ closure {a : ℝ | ¬ a ≤ (1 : ℝ) / 2} := hx.2
    rw [show {a : ℝ | ¬a ≤ (1 : ℝ) / 2} = Set.Ioi ((1 : ℝ) / 2) from by ext; simp [not_le],
        closure_Ioi] at hmem
    exact ⟨hmem, hx.1.2⟩
  refine h_left.if ?_ h_right
  intro a ⟨_, ha⟩
  rw [show frontier {b : ℝ | b ≤ (1 : ℝ) / 2} = {(1 : ℝ) / 2} from frontier_Iic] at ha
  simp only [Set.mem_singleton_iff] at ha
  simp [ha, hα'_deriv, hβ'_deriv]

/-- If `v : ℝ → ℂ` is continuous on $[0, 1]$, then for any `c : ℂ` the function
$t \mapsto c + \int_0^t v(s)\,\mathrm{d}s$ is $C^1$ on $[0, 1]$, with derivative `v`. -/
theorem c1_const_add_indefinite_integral
    (c : ℂ) (v : ℝ → ℂ)
    (hv : ContinuousOn v (Set.Icc 0 1)) :
    ContDiffOn ℝ 1 (fun t : ℝ => c + ∫ s in (0 : ℝ)..t, v s) (Set.Icc 0 1) := by
  apply ContDiffOn.add contDiffOn_const
  let vr : Set.Icc (0 : ℝ) 1 → ℂ := Set.restrict (Set.Icc 0 1) v
  have hvr : Continuous vr := hv.restrict
  let w : ℝ → ℂ := Set.IccExtend (by norm_num : (0 : ℝ) ≤ 1) vr
  have hw : Continuous w := hvr.Icc_extend'
  have hwv : ∀ t ∈ Set.Icc (0 : ℝ) 1, w t = v t := fun t ht =>
    Set.IccExtend_of_mem _ vr ht
  have heq : ∀ t ∈ Set.Icc (0 : ℝ) 1,
      (∫ s in (0 : ℝ)..t, v s) = ∫ s in (0 : ℝ)..t, w s := by
    intro t ht
    apply intervalIntegral.integral_congr
    intro s hs
    rw [Set.uIcc_of_le ht.1] at hs
    exact (hwv s ⟨hs.1, hs.2.trans ht.2⟩).symm
  have key : ∀ t ∈ Set.Icc (0 : ℝ) 1,
      HasDerivWithinAt (fun t => ∫ s in (0 : ℝ)..t, v s) (v t) (Set.Icc 0 1) t := by
    intro t ht
    have hDw : HasDerivAt (fun u => ∫ s in (0 : ℝ)..u, w s) (w t) t :=
      intervalIntegral.integral_hasDerivAt_right (hw.intervalIntegrable 0 t)
        (hw.stronglyMeasurableAtFilter _ _) hw.continuousAt
    rw [hwv t ht] at hDw
    exact hDw.hasDerivWithinAt.congr_of_mem (fun u hu => heq u hu) ht
  rw [contDiffOn_one_iff_derivWithin (uniqueDiffOn_Icc (by norm_num : (0 : ℝ) < 1))]
  exact ⟨fun t ht => (key t ht).differentiableWithinAt,
    hv.congr fun t ht =>
      (key t ht).derivWithin (uniqueDiffOn_Icc (by norm_num : (0 : ℝ) < 1) t ht)⟩

/-- The piecewise-FTC primitive
$$t \mapsto \alpha'(0) + \int_0^t v(s)\,\mathrm{d}s,\quad
v(s) = \begin{cases} 2\,\alpha''(2s) & s \le 1/2 \\ 2\,\beta''(2s-1) & s > 1/2 \end{cases}$$
is $C^1$ on $[0, 1]$, given $C^1$ paths `α'`, `β'` with flat endpoints at the join. -/
theorem flat_concat_ftc_smooth
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContDiffOn ℝ 1
      (fun t : ℝ => α' 0 + ∫ s in (0 : ℝ)..t,
        (if s ≤ (1 : ℝ) / 2
          then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1)))
      (Set.Icc 0 1) := by
  have h_cont := piecewise_velocity_continuous_on_icc hα' hβ' hα'_deriv hβ'_deriv
  exact c1_const_add_indefinite_integral (α' 0) _ h_cont

/-- **Smoothness of the piecewise-concatenation integral**: given $C^1$ paths `α'`, `β'` on
$[0, 1]$ with matching endpoints (`α' 1 = β' 0`) and flat derivatives at the join
(`derivWithin α' (Icc 0 1) 1 = 0`, `derivWithin β' (Icc 0 1) 0 = 0`), the piecewise
integral primitive is $C^1$ on $[0, 1]$.

The avoidance hypotheses `_hQ_an`, `_hα'_avoid`, `_hβ'_avoid` are not used in the proof;
they are present so that sibling lemmas may pass them to this declaration uniformly. -/
theorem contDiffOn_piecewiseConcat_integral
    {Q : ℂ → ℂ} {a : ℂ}
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContDiffOn ℝ 1
      (fun t : ℝ => α' 0 + ∫ s in (0 : ℝ)..t,
        (if s ≤ (1 : ℝ) / 2
          then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1)))
      (Set.Icc 0 1) := flat_concat_ftc_smooth hα' hβ' h_match hα'_deriv hβ'_deriv

end Library.Analysis.ResidueTheorem.PathConcatSmoothness
