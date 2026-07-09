import Mathlib
import Library.Analysis.ResidueTheorem.PathConcatLeftHalf
import Library.Analysis.ResidueTheorem.PathConcatRightHalf
import Library.Analysis.ResidueTheorem.PathConcatSmoothness
import Library.Analysis.ResidueTheorem.PathReparamIntegral

/-!
# Path concatenation and integral additivity

This module proves that the complex line integral along the concatenation of two $C^1$ paths
equals the sum of the integrals along each component path.

The key steps are:
1. Split the piecewise-constant-speed path integral at $t = 1/2$ using interval additivity.
2. Identify each half-integral with the corresponding component integral via a linear change of
   variables.
3. Reparametrize arbitrary $C^1$ paths to have vanishing endpoint derivatives, enabling the
   piecewise construction.

## Main statements

- `flat_ftc_int_additivity_at_half`: the integral of the flat-concatenated path over $[0,1]$
  splits as the sum of integrals over $[0, 1/2]$ and $[1/2, 1]$.
- `flat_ftc_right_half_int_eq`: the right-half integral of the flat concatenation equals the
  integral along `β'` over $[0,1]$.
- `flat_concat_ftc_integral_split`: the full integral along the flat-ended concatenation equals
  the sum of the two component integrals.
- `concat_flat_paths_integral_split`: given two flat-ended matching $C^1$ paths, there exists a
  $C^1$ path whose integral equals the sum of the individual integrals.
- `c1_path_concat_integral_sum_cont`: for any two matching $C^1$ paths `α` and `β`, there exists
  a $C^1$ path whose complex line integral with respect to `Q` equals the sum of the integrals
  along `α` and `β` individually.
-/

open Library.Analysis.ResidueTheorem.PathConcatLeftHalf
open Library.Analysis.ResidueTheorem.PathConcatRightHalf
open Library.Analysis.ResidueTheorem.PathConcatSmoothness
open Library.Analysis.ResidueTheorem.PathReparamIntegral

namespace Library.Analysis.ResidueTheorem.PathConcatSum

/-- Interval additivity of the flat-concatenated path integral at the midpoint $t = 1/2$.

Given two $C^1$ paths `α'` and `β'` on $[0,1]$ with `α' 1 = β' 0` and vanishing endpoint
derivatives, the integral of `Q ∘ γ · γ'` over $[0,1]$ (where `γ` is the flat piecewise
concatenation) equals the sum of integrals over $[0, 1/2]$ and $[1/2, 1]$. -/
theorem flat_ftc_int_additivity_at_half
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
    (∫ t in (0:ℝ)..1,
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
      (∫ t in (0:ℝ)..(1/2:ℝ),
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) +
      (∫ t in ((1/2:ℝ))..1,
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) := by
  have h1 :=
    flat_ftc_intintegrable_left_half hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h2 :=
    flat_ftc_intervalIntegrable_right_half hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  exact (intervalIntegral.integral_add_adjacent_intervals h1 h2).symm

/-- The right-half integral of the flat-concatenated path equals the integral along `β'`.

Let `γ` be the piecewise flat concatenation of `α'` and `β'`. This lemma identifies
$\int_{1/2}^{1} Q(\gamma(t)) \cdot \gamma'(t) \, dt$ with
$\int_0^1 Q(\beta'(t)) \cdot (\beta')'(t) \, dt$ via the substitution $u = 2t - 1$.

The proof abstracts the piecewise primitive `h` (shown $C^1$ by `flat_concat_ftc_smooth`),
identifies `h t = β' (2t - 1)` on $[1/2, 1]$ via the right-half FTC evaluation, and applies
`subst_h_eq_beta_right_half`. -/
theorem flat_ftc_right_half_int_eq
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
    (∫ t in ((1/2:ℝ))..1,
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
      (∫ t in (0:ℝ)..1, Q (β' t) * deriv β' t) := by
  have hh_smooth := flat_concat_ftc_smooth hα' hβ' h_match hα'_deriv hβ'_deriv
  have hh_eq := flat_concat_ftc_right_half hα' hβ' h_match hα'_deriv hβ'_deriv
  exact subst_h_eq_beta_right_half (Q := Q) hβ' hh_smooth hh_eq

/-- The integral along the flat-ended concatenation equals the sum of the two component integrals.

Given flat-ended $C^1$ paths `α'` and `β'` with `α' 1 = β' 0`, the integral of `Q ∘ γ · γ'`
over $[0,1]$ (where `γ` is the flat piecewise concatenation) equals
$\int_0^1 Q(\alpha'(t)) \cdot (\alpha')'(t) \, dt + \int_0^1 Q(\beta'(t)) \cdot (\beta')'(t) \, dt$.

The proof splits at $t = 1/2$ via `flat_ftc_int_additivity_at_half`, then identifies the two
halves with the component integrals via `flat_ftc_left_half_int_eq` and
`flat_ftc_right_half_int_eq`. -/
theorem flat_concat_ftc_integral_split
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
    (∫ t in (0:ℝ)..1,
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
        (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0:ℝ)..1, Q (β' t) * deriv β' t) := by
  have h_add :=
    flat_ftc_int_additivity_at_half hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_left :=
    flat_ftc_left_half_int_eq hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_right :=
    flat_ftc_right_half_int_eq hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  rw [h_add, h_left, h_right]

/-- Given two flat-ended matching $C^1$ paths, there exists a $C^1$ concatenation whose integral
is the sum of the component integrals.

More precisely, given `α'` and `β'` with `α' 1 = β' 0` and vanishing endpoint derivatives,
there exists a $C^1$ path `αβ` on $[0,1]$ with `αβ 0 = α' 0`, `αβ 1 = β' 1`, avoiding `a`,
and satisfying
$$\int_0^1 Q(\alpha\beta(t)) \cdot (\alpha\beta)'(t) \, dt =
  \int_0^1 Q(\alpha'(t)) \cdot (\alpha')'(t) \, dt +
  \int_0^1 Q(\beta'(t)) \cdot (\beta')'(t) \, dt.$$

The path `αβ` is the flat piecewise concatenation given by the integral primitive. -/
theorem concat_flat_paths_integral_split
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
    ∃ αβ : ℝ → ℂ,
      ContDiffOn ℝ 1 αβ (Set.Icc 0 1) ∧
      αβ 0 = α' 0 ∧
      αβ 1 = β' 1 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, αβ t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (αβ t) * deriv αβ t) =
        (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t) := by
  have h_smooth :
      ContDiffOn ℝ 1
        (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        (Set.Icc 0 1) :=
    flat_concat_ftc_smooth hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_left :
      ∀ t ∈ Set.Icc (0:ℝ) (1/2),
        α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = α' (2*t) :=
    flat_concat_ftc_left_half hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_right :
      ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
        α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = β' (2*t - 1) :=
    flat_concat_ftc_right_half hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_split :
      (∫ t in (0:ℝ)..1, Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
        deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
        (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0:ℝ)..1, Q (β' t) * deriv β' t) :=
    flat_concat_ftc_integral_split hQ_an hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  refine ⟨fun t => α' 0 + ∫ s in (0:ℝ)..t,
            (if s ≤ (1:ℝ)/2
              then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
              else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)),
          h_smooth, ?_, ?_, ?_, h_split⟩
  · simp
  · have h := h_right 1 ⟨by norm_num, le_refl 1⟩
    change α' 0 + _ = β' 1
    rw [h]; norm_num
  · intro t ht
    change α' 0 + _ ≠ a
    rcases le_or_gt t ((1:ℝ)/2) with htL | htR
    · rw [h_left t ⟨ht.1, htL⟩]
      exact hα'_avoid (2*t) ⟨by linarith [ht.1], by linarith⟩
    · rw [h_right t ⟨le_of_lt htR, ht.2⟩]
      exact hβ'_avoid (2*t - 1) ⟨by linarith, by linarith [ht.2]⟩

/-- **Path concatenation integral sum**: for any two matching $C^1$ paths, there exists a $C^1$
concatenation whose complex line integral equals the sum of the individual integrals.

Given $C^1$ paths `α` and `β` on $[0,1]$ with `α 1 = β 0`, both avoiding the singularity `a`,
this produces a $C^1$ path `αβ` with `αβ 0 = α 0`, `αβ 1 = β 1`, also avoiding `a`, and
$$\int_0^1 Q(\alpha\beta(t)) \cdot (\alpha\beta)'(t) \, dt =
  \int_0^1 Q(\alpha(t)) \cdot \alpha'(t) \, dt + \int_0^1 Q(\beta(t)) \cdot \beta'(t) \, dt.$$

The proof reparametrizes `α` and `β` to have vanishing endpoint derivatives via
`c1_path_smooth_reparam_flat_endpoints` (preserving endpoints and integrals), then applies
`concat_flat_paths_integral_split` to glue the flat-ended pair. -/
theorem c1_path_concat_integral_sum_cont
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α β : ℝ → ℂ}
    (hα : ContDiffOn ℝ 1 α (Set.Icc 0 1))
    (hα_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α t ≠ a)
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a)
    (h_match : α 1 = β 0) :
    ∃ αβ : ℝ → ℂ,
      ContDiffOn ℝ 1 αβ (Set.Icc 0 1) ∧
      αβ 0 = α 0 ∧
      αβ 1 = β 1 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, αβ t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (αβ t) * deriv αβ t) =
        (∫ t in (0 : ℝ)..1, Q (α t) * deriv α t) +
        (∫ t in (0 : ℝ)..1, Q (β t) * deriv β t) := by
  have h_reparam_alpha := c1_path_smooth_reparam_flat_endpoints (Q := Q) hα hα_avoid
  have h_reparam_beta := c1_path_smooth_reparam_flat_endpoints (Q := Q) hβ hβ_avoid
  obtain ⟨α', hα'_cdf, hα'0, hα'1, _hα'_d0, hα'_d1, hα'_av, hα'_int⟩ :=
    h_reparam_alpha
  obtain ⟨β', hβ'_cdf, hβ'0, hβ'1, hβ'_d0, _hβ'_d1, hβ'_av, hβ'_int⟩ :=
    h_reparam_beta
  have h_match' : α' 1 = β' 0 := by rw [hα'1, hβ'0]; exact h_match
  have h_concat :=
    concat_flat_paths_integral_split (Q := Q) hQ_an
      hα'_cdf hα'_av hβ'_cdf hβ'_av h_match' hα'_d1 hβ'_d0
  obtain ⟨αβ, hαβ_cdf, hαβ0, hαβ1, hαβ_av, hαβ_int⟩ := h_concat
  refine ⟨αβ, hαβ_cdf, ?_, ?_, hαβ_av, ?_⟩
  · rw [hαβ0, hα'0]
  · rw [hαβ1, hβ'1]
  · rw [hαβ_int, hα'_int, hβ'_int]

end Library.Analysis.ResidueTheorem.PathConcatSum
