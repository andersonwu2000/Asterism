import Library.Analysis.ResidueTheorem.CellQuadIdentity
import Library.Analysis.ResidueTheorem.HomotopyGrid
import Library.Analysis.ResidueTheorem.PathIntegralFTC

/-!
# Path integral vanishing via continuous null-homotopy

This module proves that the contour integral of an analytic function along a closed $C^1$
curve in a simply connected open subset of `ℂ` vanishes, by discretizing a continuous
null-homotopy via a Lebesgue grid and telescoping cell-boundary cancellations.

## Main statements

* `chord_segment_form_primdiff`: the integral of `f` along the chord from `z` to `w` inside
  a ball equals `F w - F z`, where `F` is a holomorphic primitive of `f` on the ball.
* `chord_int_primdiff_lerp_form`: lerp-parametrization variant of `chord_segment_form_primdiff`.
* `path_integral_split_subintervals`: splits a path integral into a sum over sub-intervals
  `[j/N, (j+1)/N]`.
* `gamma_segment_int_eq_chord_int`: each sub-path integral equals the corresponding chord
  integral.
* `gamma_int_eq_chord_polygon`: rewrites the full path integral as a chord-polygon sum.
* `path_int_zero_given_homotopy_grid`: path integral vanishes given a homotopy grid.
* `path_int_zero_from_continuous_null_homotopy`: path integral vanishes given a continuous
  null-homotopy.
* `analytic_remainder_path_integral_zero`: the contour integral of an analytic function along
  a closed $C^1$ curve in a simply connected open set vanishes.
-/

open Library.Analysis.ResidueTheorem.CellQuadIdentity
open Library.Analysis.ResidueTheorem.HomotopyGrid
open Library.Analysis.ResidueTheorem.PathIntegralFTC

namespace Library.Analysis.ResidueTheorem.PathIntegralZero

/-- The integral of `f` along the chord from `z` to `w` within `Metric.ball z₀ R` equals
`F w - F z`, where `F` is a holomorphic primitive of `f` on the ball. The proof applies the
fundamental theorem of calculus to the composition `t ↦ F (z + t * (w - z))` over `[0, 1]`. -/
theorem chord_segment_form_primdiff
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    {z w : ℂ}
    (hz : z ∈ Metric.ball z₀ R)
    (hw : w ∈ Metric.ball z₀ R) :
    (∫ s in (0:ℝ)..1, f (z + (s:ℂ) * (w - z)) * (w - z)) = F w - F z := by
  have h_cont : ContinuousOn (fun t : ℝ => F (z + (t:ℂ) * (w - z))) (Set.Icc 0 1) := by
    apply ContinuousOn.comp
    · exact (DifferentiableOn.continuousOn
        (fun x hx => (hF x hx).differentiableAt.differentiableWithinAt))
    · exact (by fun_prop : Continuous (fun t : ℝ => z + (t : ℂ) * (w - z))).continuousOn
    · intro t ht
      exact (convex_ball z₀ R).add_smul_sub_mem hz hw ht
  have h_deriv : ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun t : ℝ => F (z + (t:ℂ) * (w - z)))
        (f (z + (t:ℂ) * (w - z)) * (w - z)) t := by
    intro t ht
    have hmem : z + (t:ℂ) * (w - z) ∈ Metric.ball z₀ R := by
      have h : (1 - (t:ℝ)) • z + (t:ℝ) • w ∈ Metric.ball z₀ R :=
        (convex_ball z₀ R) hz hw (sub_nonneg.mpr ht.2.le) ht.1.le (by ring)
      simp only [RCLike.real_smul_eq_coe_mul] at h
      have heq : ((1 - (t:ℝ) : ℝ) : ℂ) * z + ((t:ℝ) : ℂ) * w = z + (t:ℂ) * (w - z) := by
        push_cast; ring
      rw [← heq]; exact h
    have hFder : HasDerivAt F (f (z + ↑t * (w - z))) (z + ↑t * (w - z)) := hF _ hmem
    have hGs : HasDerivAt (fun s : ℂ => z + s * (w - z)) (w - z) (t : ℂ) := by
      have h1 : HasDerivAt (fun s : ℂ => s * (w - z)) (1 * (w - z)) (t : ℂ) :=
        (hasDerivAt_id (t : ℂ)).mul_const (w - z)
      simp only [one_mul] at h1
      exact h1.const_add z
    exact (hFder.comp (t : ℂ) hGs).comp_ofReal
  have h_int : IntervalIntegrable (fun t : ℝ => f (z + (t:ℂ) * (w - z)) * (w - z))
      MeasureTheory.volume 0 1 := by
    have hFdiff : DifferentiableOn ℂ F (Metric.ball z₀ R) :=
      fun x hx => (hF x hx).differentiableAt.differentiableWithinAt
    have hFnhd : AnalyticOnNhd ℂ F (Metric.ball z₀ R) :=
      hFdiff.analyticOnNhd Metric.isOpen_ball
    have hfcont : ContinuousOn f (Metric.ball z₀ R) := by
      apply (hFnhd.deriv_of_isOpen Metric.isOpen_ball).continuousOn.congr
      intro x hx
      exact (hF x hx).deriv.symm
    have hmaps : Set.MapsTo (fun t : ℝ => z + (t : ℂ) * (w - z)) (Set.Icc 0 1)
        (Metric.ball z₀ R) := by
      intro t ht
      have heq : z + (t : ℂ) * (w - z) = (1 - t) • z + t • w := by
        simp only [Complex.real_smul]; push_cast; ring
      change z + (t : ℂ) * (w - z) ∈ Metric.ball z₀ R
      rw [heq]
      exact (convex_ball z₀ R) hz hw (by linarith [ht.2]) ht.1 (by linarith)
    have hcont : ContinuousOn (fun t : ℝ => f (z + (t : ℂ) * (w - z)) * (w - z))
        (Set.Icc 0 1) :=
      (hfcont.comp
        (continuousOn_const.add
          (Complex.continuous_ofReal.continuousOn.mul continuousOn_const))
        hmaps).mul continuousOn_const
    exact hcont.intervalIntegrable_of_Icc (by norm_num)
  have h_ftc := intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le
    (a := 0) (b := 1) zero_le_one h_cont h_deriv h_int
  have h0 : z + ((0:ℝ):ℂ) * (w - z) = z := by push_cast; ring
  have h1 : z + ((1:ℝ):ℂ) * (w - z) = w := by push_cast; ring
  rw [h0, h1] at h_ftc
  exact h_ftc

/-- Variant of `chord_segment_form_primdiff` using the lerp parametrization
`(1 - s) * z + s * w` instead of `z + s * (w - z)`. The two parametrizations coincide
pointwise by `ring`, and the result follows via `intervalIntegral.integral_congr`. -/
theorem chord_int_primdiff_lerp_form
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    {z w : ℂ}
    (hz : z ∈ Metric.ball z₀ R)
    (hw : w ∈ Metric.ball z₀ R) :
    (∫ s in (0:ℝ)..1, f ((1 - (s:ℂ)) * z + (s:ℂ) * w) * (w - z)) = F w - F z := by
  have h_seg : (∫ s in (0:ℝ)..1, f (z + (s:ℂ) * (w - z)) * (w - z)) = F w - F z :=
    chord_segment_form_primdiff hF hz hw
  have h_pointwise : ∀ s ∈ Set.uIcc (0:ℝ) 1,
      f ((1 - (s:ℂ)) * z + (s:ℂ) * w) * (w - z)
        = f (z + (s:ℂ) * (w - z)) * (w - z) := by
    intro s _
    congr 2
    ring
  calc (∫ s in (0:ℝ)..1, f ((1 - (s:ℂ)) * z + (s:ℂ) * w) * (w - z))
      = (∫ s in (0:ℝ)..1, f (z + (s:ℂ) * (w - z)) * (w - z)) :=
        intervalIntegral.integral_congr h_pointwise
    _ = F w - F z := h_seg

/-- Splits the path integral $\int_0^1 g(\gamma(t))\,\gamma'(t)\,dt$ into a finite sum of
integrals over the adjacent sub-intervals $[j/N, (j+1)/N]$ for $j = 0,\ldots,N-1$, via
`intervalIntegral.sum_integral_adjacent_intervals`. -/
theorem path_integral_split_subintervals
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (N : ℕ) (hNpos : 0 < N) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) =
      ∑ j ∈ Finset.range N,
        (∫ t in ((j:ℝ)/N)..(((j:ℝ)+1)/N), g (γ t) * deriv γ t) := by
  have hNpos' : (0 : ℝ) < N := Nat.cast_pos.mpr hNpos
  have hN_ne : (N : ℝ) ≠ 0 := hNpos'.ne'
  have hcont_dv : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hcont_g : ContinuousOn (fun t : ℝ => g (γ t)) (Set.Icc 0 1) :=
    hg.continuousOn.comp hγ.continuousOn (fun t ht => hmaps ht)
  have hint' : ∀ k < N, IntervalIntegrable (fun t => g (γ t) * deriv γ t)
      MeasureTheory.volume ((k : ℝ) / N) ((↑(k + 1) : ℝ) / N) := by
    intro k hk
    push_cast
    have hk1N : (k : ℝ) + 1 ≤ N := by exact_mod_cast Nat.succ_le_of_lt hk
    have hkN : (k : ℝ) / N ≤ ((k : ℝ) + 1) / N :=
      div_le_div_of_nonneg_right (by linarith) hNpos'.le
    have hsubset : Set.Icc ((k : ℝ) / N) (((k : ℝ) + 1) / N) ⊆ Set.Icc 0 1 :=
      fun t ⟨ht1, ht2⟩ =>
        ⟨le_trans (by positivity) ht1, le_trans ht2 ((div_le_one hNpos').mpr hk1N)⟩
    apply ((hcont_g.mono hsubset).mul (hcont_dv.mono hsubset)
      |>.intervalIntegrable_of_Icc hkN) |>.congr_ae
    simp only [hkN, Set.uIoc_of_le]
    rw [← MeasureTheory.restrict_Ioo_eq_restrict_Ioc]
    filter_upwards [MeasureTheory.self_mem_ae_restrict measurableSet_Ioo] with t ht
    simp only [Pi.mul_apply]
    have hmem : Set.Icc 0 1 ∈ nhds t :=
      Icc_mem_nhds (lt_of_le_of_lt (by positivity) ht.1)
                   (lt_of_lt_of_le ht.2 ((div_le_one hNpos').mpr hk1N))
    have hda : DifferentiableAt ℝ γ t :=
      (hγ.differentiableOn one_ne_zero t
        (hsubset (Set.Ioo_subset_Icc_self ht))).differentiableAt hmem
    rw [hda.derivWithin (uniqueDiffOn_Icc_zero_one t (hsubset (Set.Ioo_subset_Icc_self ht)))]
  have key := (intervalIntegral.sum_integral_adjacent_intervals
    (a := fun k => (k : ℝ) / N) (f := fun t => g (γ t) * deriv γ t) hint').symm
  simp only [Nat.cast_zero, zero_div, div_self hN_ne] at key
  simp_rw [show ∀ j : ℕ, ((j : ℝ) + 1) / N = (↑(j + 1) : ℝ) / N from
    fun j => by push_cast; ring]
  exact key

/-- The sub-path integral of `g ∘ γ` over $[j/N,(j+1)/N]$ equals the chord integral
$\int_0^1 g((1-s)\gamma(j/N)+s\,\gamma((j+1)/N))\cdot(\gamma((j+1)/N)-\gamma(j/N))\,ds$.
Both equal `F (γ ((j+1)/N)) - F (γ (j/N))` for the holomorphic primitive `F` of `g` on
the ball `Metric.ball (c 0 j) (r 0 j) ⊆ U`, which contains the entire sub-path via `hH0`. -/
theorem gamma_segment_int_eq_chord_int
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (_hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (_hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hH0 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 0 t = γ t)
    (_hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j)))
    (j : ℕ) (hj : j ∈ Finset.range N) :
    (∫ t in ((j:ℝ)/N)..(((j:ℝ)+1)/N), g (γ t) * deriv γ t) =
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
          * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N))) := by
  have hj_lt : j < N := Finset.mem_range.mp hj
  have hjN : (0 : ℝ) < N := Nat.cast_pos.mpr hNpos
  have hjle : ((j:ℝ)/N) ≤ (((j:ℝ)+1)/N) := by
    have h := one_div_nonneg.mpr (le_of_lt hjN)
    have heq : ((j:ℝ)+1)/N - (j:ℝ)/N = 1/N := by
      field_simp; ring
    linarith
  have hsub_Icc : Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N) ⊆ Set.Icc (0:ℝ) 1 := by
    intro t ht
    refine ⟨?_, ?_⟩
    · have h0 : (0:ℝ) ≤ (j:ℝ)/N := by positivity
      linarith [ht.1]
    · have h2 : ((j:ℝ)+1)/N ≤ 1 := by
        rw [div_le_one hjN]; exact_mod_cast hj_lt
      linarith [ht.2]
  obtain ⟨hrpos, hrsub, hrτt⟩ := hgrid 0 j hNpos hj_lt
  have hf_diff : DifferentiableOn ℂ g (Metric.ball (c 0 j) (r 0 j)) :=
    (hg.mono hrsub).differentiableOn
  have hγ_seg : ContDiffOn ℝ 1 γ (Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N)) :=
    hγ.mono hsub_Icc
  have h0_in : (0:ℝ) ∈ Set.Icc (((0:ℕ):ℝ)/N) ((((0:ℕ):ℝ)+1)/N) := by
    constructor
    · simp
    · positivity
  have hγU_seg : Set.MapsTo γ (Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N))
      (Metric.ball (c 0 j) (r 0 j)) := by
    intro t ht
    have ht01 : t ∈ Set.Icc (0:ℝ) 1 := hsub_Icc ht
    have hHt := hrτt 0 h0_in t ht
    rw [hH0 t ht01] at hHt
    exact hHt
  obtain ⟨F, hF, hgamma_eq⟩ :=
    integral_eq_sub_of_differentiableOn_ball hjle hf_diff hγ_seg hγU_seg
  have hzmem : γ ((j:ℝ)/N) ∈ Metric.ball (c 0 j) (r 0 j) :=
    hγU_seg ⟨le_refl _, hjle⟩
  have hwmem : γ (((j:ℝ)+1)/N) ∈ Metric.ball (c 0 j) (r 0 j) :=
    hγU_seg ⟨hjle, le_refl _⟩
  have hchord := chord_int_primdiff_lerp_form hF hzmem hwmem
  rw [hgamma_eq, ← hchord]

/-- Rewrites the path integral $\int_0^1 g(\gamma(t))\,\gamma'(t)\,dt$ as the sum of chord
integrals over the $N$-vertex polygon $(\gamma(j/N))_{j=0,\ldots,N}$. Each sub-path integral
over $[j/N,(j+1)/N]$ equals the corresponding chord integral because both lie inside the ball
`Metric.ball (c 0 j) (r 0 j) ⊆ U`, where `g` has a holomorphic primitive. -/
theorem gamma_int_eq_chord_polygon
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (_hclosed : γ 0 = γ 1)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hH0 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 0 t = γ t)
    (_hH1 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 1 t = γ 0)
    (_hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (_hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) =
      ∑ j ∈ Finset.range N,
        (∫ s in (0:ℝ)..1,
          g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
            * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N))) := by
  have hsplit := path_integral_split_subintervals hU hg hγ hmaps N hNpos
  have hseg : ∀ j ∈ Finset.range N,
      (∫ t in ((j:ℝ)/N)..(((j:ℝ)+1)/N), g (γ t) * deriv γ t) =
        (∫ s in (0:ℝ)..1,
          g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
            * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N))) := by
    intro j hj
    exact gamma_segment_int_eq_chord_int hU hg hγ hmaps hHcont hH0 hHmaps
      N hNpos c r hgrid j hj
  rw [hsplit]
  exact Finset.sum_congr rfl hseg

/-- The path integral of an analytic function along a closed $C^1$ curve vanishes given a
homotopy grid. The proof uses `gamma_int_eq_chord_polygon` to reduce to a chord-polygon sum,
then `chord_polygon_int_zero` to show the sum vanishes by telescoping cell-boundary
cancellations, each cell integrating to zero by Cauchy's theorem on the covering ball. -/
theorem path_int_zero_given_homotopy_grid
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hH0 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 0 t = γ t)
    (hH1 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 1 t = γ 0)
    (hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 := by
  have h_eq := gamma_int_eq_chord_polygon hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  have h_zero := chord_polygon_int_zero hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  exact h_eq.trans h_zero

/-- The contour integral of an analytic function along a null-homotopic closed $C^1$ curve
vanishes. The continuous null-homotopy `H` is discretized via `homotopy_lebesgue_grid`, which
extracts `N` and per-cell balls in `U` covering `H`; `path_int_zero_given_homotopy_grid` then
telescopes the cell-boundary cancellations to conclude. -/
theorem path_int_zero_from_continuous_null_homotopy
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1)
    (H : ℝ → ℝ → ℂ)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hH0 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 0 t = γ t)
    (hH1 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 1 t = γ 0)
    (hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 := by
  obtain ⟨N, hNpos, c, r, hgrid⟩ :=
    homotopy_lebesgue_grid (U := U) (H := H) hU hHcont hHmaps
  exact path_int_zero_given_homotopy_grid (U := U) (g := g) (γ := γ) (H := H)
    hU hg hγ hmaps hclosed hHcont hH0 hH1 hHleft hHright hHmaps
    N hNpos c r hgrid

/-- **Path integral vanishing in a simply connected domain**: the contour integral of an
analytic function `g` along a closed $C^1$ curve `γ` in a simply connected open set `U ⊆ ℂ`
vanishes. The proof extracts a continuous null-homotopy from `SimplyConnectedSpace` and
applies `path_int_zero_from_continuous_null_homotopy`. -/
theorem analytic_remainder_path_integral_zero
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 := by
  obtain ⟨H, hHcont, hH0, hH1, hHleft, hHright, hHmaps⟩ :=
    simply_connected_continuous_null_homotopy_of_loop hU hSC hγ hmaps hclosed
  exact path_int_zero_from_continuous_null_homotopy hU hg hγ hmaps hclosed
    H hHcont hH0 hH1 hHleft hHright hHmaps

end Library.Analysis.ResidueTheorem.PathIntegralZero
