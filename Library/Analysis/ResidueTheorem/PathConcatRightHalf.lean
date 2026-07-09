import Mathlib
import Library.Analysis.ResidueTheorem.PathConcatLeftHalf
import Library.Analysis.ResidueTheorem.PathConcatPiecewiseSplit

open Library.Analysis.ResidueTheorem.PathConcatLeftHalf
open Library.Analysis.ResidueTheorem.PathConcatPiecewiseSplit

/-!
# Right-half path splitting for the Residue Theorem

This file develops the analytic and integration lemmas for the right-half branch of a
piecewise-linear path concatenation, as needed for the proof of the Residue Theorem.

Given two $C^1$ paths $\alpha', \beta' : [0,1] \to \mathbb{C}$ with $\alpha'(1) = \beta'(0)$,
we study the flat-concatenated path on $[1/2, 1]$, whose value at $t$ is $\beta'(2t - 1)$.

## Main statements

- `right_integrand_cont_on_icc`: The integrand `2 · β'_{[0,1]}'(2s - 1)` is continuous on
  `[1/2, 1]` whenever `β'` is $C^1$ on `[0, 1]`.
- `ftc_const_add_right_half`: Abstract FTC: `fun u => C + ∫_(1/2)^u g` has derivative `g(t)`
  at every `t ∈ (1/2, 1)` for `g` continuous on `[1/2, 1]`.
- `flat_concat_ftc_right_half`: The flat-concatenated path evaluates to `β'(2t - 1)` on
  `[1/2, 1]`.
- `subst_h_eq_beta_right_half`: Change of variables — the contour integral over a path `h`
  agreeing with `β'(2 · - 1)` on `[1/2, 1]` equals the integral over `β'` on `[0, 1]`.
- `flat_ftc_intervalIntegrable_right_half`: Interval integrability of the full integrand on
  the right half.
-/

namespace Library.Analysis.ResidueTheorem.PathConcatRightHalf

/-- The right-half integrand `fun s => 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)` is
continuous on `Set.Icc (1/2) 1`.  This follows from `ContDiffOn ℝ 1 β'` by composing the
continuous derivative with the affine map $s \mapsto 2s - 1$. -/
theorem right_integrand_cont_on_icc {β' : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ContinuousOn (fun s : ℝ => 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      (Set.Icc (1/2 : ℝ) 1) := by
  have hderiv : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hmap : Set.MapsTo (fun s : ℝ => 2*s - 1) (Set.Icc (1/2 : ℝ) 1) (Set.Icc 0 1) := by
    intro s hs
    simp only [Set.mem_Icc] at hs ⊢
    constructor <;> linarith [hs.1, hs.2]
  have hlin : ContinuousOn (fun s : ℝ => 2*s - 1) (Set.Icc (1/2 : ℝ) 1) :=
    ((continuous_const.mul continuous_id).sub continuous_const).continuousOn
  exact continuousOn_const.mul (hderiv.comp hlin hmap)

/-- Abstract FTC for the right half: for `g` continuous on `Set.Icc (1/2) 1` and any constant
`C : ℂ`, the function `fun u => C + ∫ s in (1/2)..u, g s` has derivative `g t` at every
`t ∈ Set.Ioo (1/2) 1`.

The proof upgrades `ContinuousOn` to `ContinuousAt` via `Icc_mem_nhds`, establishes
`IntervalIntegrable` and `StronglyMeasurableAtFilter`, then applies
`intervalIntegral.integral_hasDerivAt_right` followed by `HasDerivAt.const_add`. -/
theorem ftc_const_add_right_half {g : ℝ → ℂ}
    (hg : ContinuousOn g (Set.Icc (1 / 2 : ℝ) 1)) (C : ℂ) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      HasDerivAt (fun u : ℝ => C + ∫ s in ((1:ℝ)/2)..u, g s) (g t) t := by
  intro t ht
  have hIcc : Set.Icc (1/2 : ℝ) 1 ∈ nhds t := Icc_mem_nhds ht.1 ht.2
  have ht_mem : t ∈ Set.Icc (1/2 : ℝ) 1 := ⟨ht.1.le, ht.2.le⟩
  have hCt : ContinuousAt g t := (hg t ht_mem).continuousAt hIcc
  have hII : IntervalIntegrable g MeasureTheory.volume (1/2) t :=
    (hg.mono (Set.Icc_subset_Icc_right ht.2.le)).intervalIntegrable_of_Icc ht.1.le
  have hSMF : StronglyMeasurableAtFilter g (nhds t) MeasureTheory.volume :=
    (hg.mono Set.Ioo_subset_Icc_self).stronglyMeasurableAtFilter isOpen_Ioo t ht
  have hDR : HasDerivAt (fun u => ∫ s in ((1:ℝ)/2)..u, g s) (g t) t :=
    intervalIntegral.integral_hasDerivAt_right hII hSMF hCt
  exact hDR.const_add C

/-- The piecewise flat-concatenated path has derivative `2 * derivWithin β' (Set.Icc 0 1) (2t-1)`
at every `t ∈ Set.Ioo (1/2) 1`.

Two-step proof: (1) `right_integrand_cont_on_icc` gives continuity of the integrand
`2 · β'_{[0,1]}'(2s-1)` on `[1/2, 1]`; (2) `ftc_const_add_right_half` applies the abstract FTC
specialised to `g := 2 · β'_{[0,1]}'(2s-1)` and
`C := α'(0) + ∫ s in 0..(1/2), 2 · α'_{[0,1]}'(2s)`. -/
theorem right_split_has_deriv_at_on_ioo
    {α' β' : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      HasDerivAt
        (fun u : ℝ => (α' 0 + ∫ s in (0:ℝ)..((1:ℝ)/2),
                  2 * derivWithin α' (Set.Icc 0 1) (2*s)) +
          ∫ s in ((1:ℝ)/2)..u, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
        (2 * derivWithin β' (Set.Icc 0 1) (2*t - 1)) t := by
  intro t ht
  have h_cont := right_integrand_cont_on_icc hβ'
  exact ftc_const_add_right_half h_cont
    (α' 0 + ∫ s in (0:ℝ)..((1:ℝ)/2), 2 * derivWithin α' (Set.Icc 0 1) (2*s))
    t ht

/-- The piecewise integral over $[1/2, t]$ of the right-half branch equals `β'(2t - 1) - β'(0)`
for every `t ∈ Set.Icc (1/2) 1`.

The proof proceeds in five steps: (1) simplify the piecewise integrand to the right branch on
$[1/2, t]$; (2) pull out the constant factor 2; (3) apply the change of variables
$s \mapsto 2s - 1$ to reduce to $\int_0^{2t-1} \beta''$; (4) evaluate by FTC; (5) simplify
$2 \cdot 2^{-1} = 1$. -/
theorem flat_concat_right_half_piecewise_eval
    {α' β' : ℝ → ℂ}
    (_hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
      (∫ s in ((1:ℝ)/2:ℝ)..t,
        (if s ≤ (1:ℝ)/2
          then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = β' (2*t - 1) - β' 0 := by
  intro t ht
  -- Step 1: piecewise = else branch pointwise on [1/2, t]
  have h1 : ∫ s in ((1:ℝ)/2)..t,
      (if s ≤ (1:ℝ)/2 then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
       else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) =
    ∫ s in ((1:ℝ)/2:ℝ)..t, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1) := by
    apply intervalIntegral.integral_congr
    intro s hs
    simp only [Set.uIcc_of_le ht.1, Set.mem_Icc] at hs
    by_cases heq : s = 1/2
    · subst heq
      have hv1 : (2:ℝ) * (1/2:ℝ) = 1 := by norm_num
      simp only [le_refl, if_true, hv1, hα'_deriv, mul_zero, sub_self, hβ'_deriv]
    · have hs_gt : ¬ s ≤ 1/2 := not_le.mpr (lt_of_le_of_ne hs.1 (Ne.symm heq))
      simp only [hs_gt, if_false]
  rw [h1]
  -- Step 2: Pull out constant 2
  have h2 : ∫ s in ((1:ℝ)/2)..t, (2 : ℂ) * derivWithin β' (Set.Icc 0 1) (2*s - 1) =
      2 * ∫ s in ((1:ℝ)/2)..t, derivWithin β' (Set.Icc 0 1) (2*s - 1) :=
    intervalIntegral.integral_const_mul 2 _
  rw [h2]
  -- Step 3: Change of variables: ∫_{1/2}^t f(2s-1) = 2⁻¹ · ∫_0^{2t-1} f(u)
  have h3 : ∫ s in ((1:ℝ)/2)..t, derivWithin β' (Set.Icc 0 1) (2*s - 1) =
      (2:ℝ)⁻¹ • ∫ u in (0:ℝ)..(2*t - 1), derivWithin β' (Set.Icc 0 1) u := by
    have ha : ∫ s in ((1:ℝ)/2)..t, derivWithin β' (Set.Icc 0 1) (2*s - 1) =
        (2:ℝ)⁻¹ • ∫ u in ((2:ℝ) * (1/2))..(2*t), derivWithin β' (Set.Icc 0 1) (u - 1) :=
      intervalIntegral.integral_comp_mul_left
        (fun u => derivWithin β' (Set.Icc 0 1) (u - 1)) (two_ne_zero' ℝ)
    simp only [show (2:ℝ) * (1/2) = 1 from by norm_num] at ha
    rw [ha]; congr 1
    have hb : ∫ u in (1:ℝ)..(2*t), derivWithin β' (Set.Icc 0 1) (u - 1) =
        ∫ v in ((1:ℝ) - 1)..(2*t - 1), derivWithin β' (Set.Icc 0 1) v :=
      intervalIntegral.integral_comp_sub_right (derivWithin β' (Set.Icc 0 1)) 1
    simp only [show (1:ℝ) - 1 = 0 from by norm_num] at hb
    exact hb
  rw [h3]
  -- Step 4: FTC on [0, 2t-1] ⊆ [0, 1]
  have h_le : (0:ℝ) ≤ 2*t - 1 := by linarith [ht.1]
  have h_le1 : 2*t - 1 ≤ 1 := by linarith [ht.2]
  have h4 : ∫ u in (0:ℝ)..(2*t - 1), derivWithin β' (Set.Icc 0 1) u =
      β' (2*t - 1) - β' 0 := by
    have hF_cont : ContinuousOn β' (Set.Icc 0 (2*t - 1)) :=
      hβ'.continuousOn.mono (Set.Icc_subset_Icc_right h_le1)
    have hF_deriv : ∀ x ∈ Set.Ioo 0 (2*t - 1),
        HasDerivAt β' (derivWithin β' (Set.Icc 0 1) x) x := by
      intro x hx
      have hx1 : x ∈ Set.Ioo 0 1 := Set.Ioo_subset_Ioo_right h_le1 hx
      have hmem : x ∈ Set.Icc 0 1 :=
        Set.mem_Icc.mpr ⟨le_of_lt hx1.1, le_of_lt hx1.2⟩
      have hU : Set.Icc 0 1 ∈ nhds x := Icc_mem_nhds hx1.1 hx1.2
      have hda : DifferentiableAt ℝ β' x :=
        (hβ'.differentiableOn one_ne_zero x hmem).differentiableAt hU
      rw [hda.derivWithin (uniqueDiffWithinAt_of_mem_nhds hU)]
      exact hda.hasDerivAt
    have hcont_deriv : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 (2*t - 1)) :=
      (hβ'.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl).mono
        (Set.Icc_subset_Icc_right h_le1)
    exact intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le h_le hF_cont hF_deriv
      (hcont_deriv.intervalIntegrable_of_Icc h_le)
  rw [h4]
  -- Step 5: 2 * (2⁻¹ • v) = v
  rw [Complex.real_smul]
  push_cast
  ring

/-- The flat-concatenated path value equals `β'(2t - 1)` for every `t ∈ Set.Icc (1/2) 1`.

Combines `piecewise_integral_add_adjacent_half`, `flat_concat_left_half_piecewise_eval`, and
`flat_concat_right_half_piecewise_eval` to simplify the piecewise integral expression, then
uses the matching condition `α'(1) = β'(0)`. -/
theorem flat_concat_ftc_right_half
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
      α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = β' (2*t - 1) := by
  intro t ht
  have hA :=
    piecewise_integral_add_adjacent_half hα' hβ' h_match hα'_deriv hβ'_deriv t ht
  have hB :=
    flat_concat_left_half_piecewise_eval hα' hβ' h_match hα'_deriv hβ'_deriv
  have hC :=
    flat_concat_right_half_piecewise_eval hα' hβ' h_match hα'_deriv hβ'_deriv t ht
  rw [hA, hB, hC, h_match]
  ring

/-- Restricts `flat_concat_ftc_right_half` from `Set.Icc (1/2) 1` to the open interior
`Set.Ioo (1/2) 1`. -/
theorem right_half_path_value_eq_on_ioo
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t
        = β' (2*t - 1) := fun t ht =>
      flat_concat_ftc_right_half hα' hβ' h_match hα'_deriv hβ'_deriv t ⟨ht.1.le, ht.2.le⟩

/-- The derivative of the piecewise flat-concatenation equals `2 * derivWithin β' (Set.Icc 0 1)
(2*t - 1)` for every `t ∈ Set.Ioo (1/2) 1`.

Uses `piecewise_f_eveq_right_split_on_ioo` to show the piecewise function is eventually equal
to the split form, then transfers the derivative via `HasDerivAt.congr_of_eventuallyEq`. -/
theorem right_half_deriv_value_eq_on_ioo
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_h_match : α' 1 = β' 0)
    (_hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (_hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t
        = 2 * derivWithin β' (Set.Icc 0 1) (2*t - 1) := by
  have h_evEq := piecewise_f_eveq_right_split_on_ioo (α' := α') (β' := β') hα' hβ'
  have h_deriv := right_split_has_deriv_at_on_ioo (α' := α') (β' := β') hβ'
  intro t ht
  exact ((h_deriv t ht).congr_of_eventuallyEq (h_evEq t ht)).deriv

/-- On `Set.Ioo (1/2) 1`, the integrand of the piecewise flat-concatenation agrees with the
simplified form `fun t => Q (β' (2*t - 1)) * (2 * derivWithin β' (Set.Icc 0 1) (2*t - 1))`.

Follows by combining `right_half_path_value_eq_on_ioo` (path value) and
`right_half_deriv_value_eq_on_ioo` (derivative value). -/
theorem right_half_integrand_eq_on_ioo
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
    Set.EqOn
      (fun t : ℝ =>
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t)
      (fun t : ℝ => Q (β' (2*t - 1)) * (2 * derivWithin β' (Set.Icc 0 1) (2*t - 1)))
      (Set.Ioo (1/2 : ℝ) 1) := by
  have h_path :=
    right_half_path_value_eq_on_ioo (β' := β') hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_deriv :=
    right_half_deriv_value_eq_on_ioo (β' := β') hα' hβ' h_match hα'_deriv hβ'_deriv
  intro t ht
  change Q _ * _ = Q _ * _
  rw [h_path t ht, h_deriv t ht]

/-- For `h` agreeing with `β'(2 · - 1)` on `Set.Icc (1/2) 1`, the derivative satisfies
`deriv h t = 2 * deriv β' (2 * t - 1)` for every `t ∈ Set.Ioo (1/2) 1`.

Uses `EventuallyEq.deriv_eq` to transfer to the composition, then the chain rule via
`HasDerivAt.scomp` to compute the derivative of `β' ∘ (2 · - 1)`. -/
theorem deriv_eq_two_mul_deriv_right_half
    {β' h : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_right : ∀ t ∈ Set.Icc ((1 / 2) : ℝ) 1, h t = β' (2 * t - 1)) :
    ∀ t ∈ Set.Ioo ((1 : ℝ) / 2) 1, deriv h t = 2 * deriv β' (2 * t - 1) := by
  intro t ht
  have hneigh : Set.Ioo ((1/2 : ℝ)) 1 ∈ nhds t := isOpen_Ioo.mem_nhds ht
  have heq_f : h =ᶠ[nhds t] fun s => β' (2 * s - 1) := by
    filter_upwards [hneigh] with s hs
    exact hh_right s (Set.Ioo_subset_Icc_self hs)
  rw [heq_f.deriv_eq]
  have h2t : 2 * t - 1 ∈ Set.Ioo (0 : ℝ) 1 := by constructor <;> linarith [ht.1, ht.2]
  have hβ'_diff : DifferentiableAt ℝ β' (2 * t - 1) :=
    (hβ'.differentiableOn (by norm_num)).differentiableAt
      (Filter.mem_of_superset (isOpen_Ioo.mem_nhds h2t) Set.Ioo_subset_Icc_self)
  have hlin : HasDerivAt (fun s : ℝ => 2 * s - 1) 2 t := by
    have h1 := (hasDerivAt_id t).const_mul (2 : ℝ)
    have h2 := h1.sub (hasDerivAt_const t (1 : ℝ))
    simp only [mul_one, sub_zero] at h2
    exact h2
  have hchain : HasDerivAt (β' ∘ fun s => 2 * s - 1) ((2:ℝ) • deriv β' (2 * t - 1)) t :=
    hβ'_diff.hasDerivAt.scomp t hlin
  calc deriv (fun s => β' (2 * s - 1)) t
      = deriv (β' ∘ fun s => 2 * s - 1) t := by simp [Function.comp_def]
    _ = (2 : ℝ) • deriv β' (2 * t - 1) := hchain.deriv
    _ = 2 * deriv β' (2 * t - 1) := by
        rw [Complex.real_smul]; norm_cast

/-- The integral of `Q (h t) * deriv h t` over `[1/2, 1]` equals the integral of
`Q (β' (2*t - 1)) * (2 * deriv β' (2*t - 1))` over `[1/2, 1]`, given that
`h t = β' (2 * t - 1)` on `Set.Icc (1/2) 1`.

Uses `deriv_eq_two_mul_deriv_right_half` to rewrite the derivative a.e. on the interior, then
`intervalIntegral.integral_congr_ae_restrict` to transfer to the full interval. -/
theorem integrand_match_right_half_to_compose
    {Q : ℂ → ℂ} {β' h : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_right : ∀ t ∈ Set.Icc ((1 / 2) : ℝ) 1, h t = β' (2 * t - 1)) :
    (∫ t in ((1/2) : ℝ)..1, Q (h t) * deriv h t) =
      (∫ t in ((1/2) : ℝ)..1, Q (β' (2*t - 1)) * (2 * deriv β' (2*t - 1))) := by
  have hkey : ∀ t ∈ Set.Ioo ((1:ℝ)/2) 1, deriv h t = 2 * deriv β' (2*t - 1) :=
    deriv_eq_two_mul_deriv_right_half hβ' hh hh_right
  apply intervalIntegral.integral_congr_ae_restrict
  rw [Set.uIoc_of_le (by norm_num : ((1:ℝ)/2) ≤ 1)]
  refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict MeasureTheory.Ioo_ae_eq_Ioc ?_
  filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
  have ht_Icc : t ∈ Set.Icc ((1:ℝ)/2) 1 := Set.Ioo_subset_Icc_self ht
  rw [hh_right t ht_Icc, hkey t ht]

/-- Linear change of variables $u = 2t - 1$: the integral of `Q (β' (2*t - 1)) * (2 * deriv β'
(2*t - 1))` over `[1/2, 1]` equals the integral of `Q (β' t) * deriv β' t` over `[0, 1]`.

Uses `intervalIntegral.smul_integral_comp_mul_sub` after rewriting `a * (2 * b) = 2 • (a * b)`
and pulling the scalar factor out via `intervalIntegral.integral_smul`. -/
theorem subst_linear_2t_minus_1
    {Q : ℂ → ℂ} {β' : ℝ → ℂ} :
    (∫ t in ((1/2) : ℝ)..1, Q (β' (2*t - 1)) * (2 * deriv β' (2*t - 1))) =
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t) := by
  have h := intervalIntegral.smul_integral_comp_mul_sub
    (a := (1/2 : ℝ)) (b := (1 : ℝ)) (fun u => Q (β' u) * deriv β' u) 2 1
  simp only [show (2:ℝ) * (1/2) - 1 = 0 from by norm_num,
             show (2:ℝ) * 1 - 1 = 1 from by norm_num] at h
  have hcongr : (∫ t in ((1/2) : ℝ)..1, Q (β' (2*t - 1)) * (2 * deriv β' (2*t - 1))) =
                ∫ t in ((1/2) : ℝ)..1, (2 : ℂ) • (Q (β' (2*t - 1)) * deriv β' (2*t - 1)) := by
    refine intervalIntegral.integral_congr ?_
    intro t _
    simp only [smul_eq_mul]
    ring
  rw [hcongr]
  rw [intervalIntegral.integral_smul]
  exact h

/-- The simplified right-half integrand `fun t => Q (β' (2*t - 1)) * (2 * derivWithin β'
(Set.Icc 0 1) (2*t - 1))` is interval integrable on `[1/2, 1]`.

Proved by showing the integrand is continuous on `[1/2, 1]` via the composition of the analytic
`Q`, continuous `β'`, and continuous `derivWithin β'`, all composed with the affine map
$t \mapsto 2t - 1$. -/
theorem right_half_substituted_intervalIntegrable
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (_hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (_h_match : α' 1 = β' 0)
    (_hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (_hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    IntervalIntegrable
      (fun t : ℝ => Q (β' (2*t - 1)) * (2 * derivWithin β' (Set.Icc 0 1) (2*t - 1)))
      MeasureTheory.volume (1/2) 1 := by
  have hle : (1:ℝ)/2 ≤ 1 := by norm_num
  apply ContinuousOn.intervalIntegrable_of_Icc hle
  have hmap : Set.MapsTo (fun t : ℝ => 2*t - 1) (Set.Icc (1/2) 1) (Set.Icc 0 1) := by
    intro t ht; constructor <;> [linarith [ht.1]; linarith [ht.2]]
  have hlin : ContinuousOn (fun t : ℝ => 2*t - 1) (Set.Icc (1/2) 1) :=
    ((continuous_const.mul continuous_id').sub continuous_const).continuousOn
  have hβ'_cont : ContinuousOn β' (Set.Icc 0 1) := hβ'.continuousOn
  have hβ'_dw : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hβ'_avoids : Set.MapsTo (fun t : ℝ => β' (2*t - 1)) (Set.Icc (1/2) 1)
      (Set.univ \ {a}) := by
    intro t ht
    simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and]
    exact hβ'_avoid (2*t - 1) (hmap ht)
  apply ContinuousOn.mul
  · exact (hQ_an.continuousOn.comp (hβ'_cont.comp hlin hmap) hβ'_avoids)
  · exact (continuousOn_const.mul (hβ'_dw.comp hlin hmap))

/-- The integral of `Q (h t) * deriv h t` over `[1/2, 1]` equals the integral of
`Q (β' t) * deriv β' t` over `[0, 1]`, given that `h t = β' (2 * t - 1)` on `[1/2, 1]`.

Chains `integrand_match_right_half_to_compose` (rewrite using chain rule) and
`subst_linear_2t_minus_1` (linear substitution $u = 2t - 1$). -/
theorem subst_h_eq_beta_right_half
    {Q : ℂ → ℂ} {β' h : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_right : ∀ t ∈ Set.Icc ((1 / 2) : ℝ) 1, h t = β' (2 * t - 1)) :
    (∫ t in ((1/2) : ℝ)..1, Q (h t) * deriv h t) =
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t) := by
  have h1 := integrand_match_right_half_to_compose (Q := Q) hβ' hh hh_right
  have h2 := subst_linear_2t_minus_1 (Q := Q) (β' := β')
  exact h1.trans h2

/-- The full right-half contour integrand $Q(F(t)) \cdot F'(t)$ is interval integrable on
`[1/2, 1]`, where $F$ is the piecewise flat-concatenation.

Uses `right_half_integrand_eq_on_ioo` to equate the integrand a.e. with the simplified form
`fun t => Q (β' (2*t - 1)) * (2 * derivWithin β' (Set.Icc 0 1) (2*t - 1))`, then applies
`right_half_substituted_intervalIntegrable` for the latter. -/
theorem flat_ftc_intervalIntegrable_right_half
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    IntervalIntegrable
      (fun t : ℝ =>
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t)
      MeasureTheory.volume (1/2) 1 := by
  have h_eq_on :=
    right_half_integrand_eq_on_ioo hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_simp_ii :=
    right_half_substituted_intervalIntegrable hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  refine h_simp_ii.congr_ae ?_
  have h_uIoc : Set.uIoc (1/2 : ℝ) 1 = Set.Ioc (1/2 : ℝ) 1 :=
    Set.uIoc_of_le (by norm_num)
  rw [show Set.uIoc (1/2 : ℝ) 1 = Set.Ioc (1/2 : ℝ) 1 from h_uIoc,
      ← MeasureTheory.Measure.restrict_congr_set
        (s := Set.Ioo (1/2 : ℝ) 1) (t := Set.Ioc (1/2 : ℝ) 1) MeasureTheory.Ioo_ae_eq_Ioc]
  filter_upwards [MeasureTheory.self_mem_ae_restrict measurableSet_Ioo] with t ht
  exact (h_eq_on ht).symm

end Library.Analysis.ResidueTheorem.PathConcatRightHalf
