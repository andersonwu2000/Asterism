import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Complex.HasPrimitives

namespace Library.Analysis.ResidueTheorem.CellQuadIdentity

/-!
# Cell quadrilateral contour integral identities

This module establishes the key combinatorial-analytic identities underlying the
homotopy-invariance step in the proof of Cauchy's theorem.  A homotopy
$H : [0,1]^2 \to U$ between a closed curve $\gamma$ and the constant curve is
discretised by an $N \times N$ grid; each cell is covered by a small open ball
$B(c_{ij}, r_{ij}) \subseteq U$ on which `g` has a primitive (by analyticity).
The fundamental theorem of calculus is applied on each ball, and the resulting
segment-integral identities are telescoped — first horizontally (over columns $j$)
and then vertically (over rows $i$) — to show that the chord-polygon integral of
`g` along `γ` vanishes.

## Main statements

- `cell_quad_identity_on_ball`: closed quadrilateral integral identity via an
  antiderivative on a convex ball.
- `cell_quad_chord_vert_diff`: per-cell comparison of vertical and horizontal chord
  integrals.
- `row_polygon_consec_eq`: row-strip homotopy invariance, one step at a time.
- `row_polygon_telescope`: induction over rows bridging $\tau = 0$ and $\tau = 1$.
- `row_polygon_zero_eq_one`: equates the row-polygon sums at $\tau = 0$ and $\tau = 1$.
- `chord_polygon_eq_h_zero_row`: identifies the chord-polygon sum with the $\tau = 0$
  row-polygon sum.
- `row_polygon_one_eq_zero`: the $\tau = 1$ row-polygon sum vanishes.
- `chord_polygon_int_zero`: the chord-polygon contour integral of `g` along `γ` is zero.
-/

/-- Quadrilateral contour-integral identity on a convex ball.

Given a function `g` that is `DifferentiableOn ℂ` on `Metric.ball z₀ R` and four points
`z₁ z₂ z₃ z₄` in the ball, the identity
`∫ z₁→z₄ − ∫ z₂→z₃ = ∫ z₁→z₂ − ∫ z₄→z₃` holds (where each integral is a straight-segment
contour integral).  The proof obtains a primitive `F` of `g` via
`DifferentiableOn.isExactOn_ball`, applies the fundamental theorem of calculus to each segment,
and closes by `ring`. -/
theorem cell_quad_identity_on_ball
    {g : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hg : DifferentiableOn ℂ g (Metric.ball z₀ R))
    {z₁ z₂ z₃ z₄ : ℂ}
    (h₁ : z₁ ∈ Metric.ball z₀ R)
    (h₂ : z₂ ∈ Metric.ball z₀ R)
    (h₃ : z₃ ∈ Metric.ball z₀ R)
    (h₄ : z₄ ∈ Metric.ball z₀ R) :
    (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * z₁ + (s:ℂ) * z₄) * (z₄ - z₁))
    - (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * z₂ + (s:ℂ) * z₃) * (z₃ - z₂))
    =
    (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * z₁ + (s:ℂ) * z₂) * (z₂ - z₁))
    - (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * z₄ + (s:ℂ) * z₃) * (z₃ - z₄)) := by
  obtain ⟨F, hF⟩ := hg.isExactOn_ball
  suffices hseg : ∀ a b : ℂ, a ∈ Metric.ball z₀ R → b ∈ Metric.ball z₀ R →
      (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * a + (s:ℂ) * b) * (b - a)) = F b - F a by
    rw [hseg z₁ z₄ h₁ h₄, hseg z₂ z₃ h₂ h₃, hseg z₁ z₂ h₁ h₂, hseg z₄ z₃ h₄ h₃]
    ring
  intro a b ha hb
  have heq : ∀ s : ℝ, (1 - (s:ℂ)) * a + (s:ℂ) * b = a + (s:ℂ) * (b - a) := fun s => by ring
  simp_rw [heq]
  have hmem : Set.MapsTo (fun t : ℝ => a + (t:ℂ) * (b - a)) (Set.Icc 0 1)
      (Metric.ball z₀ R) := by
    intro t ht
    change a + (t:ℂ) * (b - a) ∈ Metric.ball z₀ R
    have h : (1 - (t:ℝ)) • a + (t:ℝ) • b ∈ Metric.ball z₀ R :=
      (convex_ball z₀ R) ha hb (sub_nonneg.mpr ht.2) ht.1 (by linarith [ht.1, ht.2])
    simp only [RCLike.real_smul_eq_coe_mul] at h
    have heq2 : ((1 - (t:ℝ) : ℝ) : ℂ) * a + ((t:ℝ) : ℂ) * b = a + (t:ℂ) * (b - a) := by
      push_cast; ring
    rwa [← heq2]
  have h_cont : ContinuousOn (fun t : ℝ => F (a + (t:ℂ) * (b - a))) (Set.Icc 0 1) := by
    apply ContinuousOn.comp
    · exact DifferentiableOn.continuousOn
        (fun x hx => (hF x hx).differentiableAt.differentiableWithinAt)
    · exact (by fun_prop : Continuous (fun t : ℝ => a + (t:ℂ) * (b - a))).continuousOn
    · exact hmem
  have h_deriv : ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun t : ℝ => F (a + (t:ℂ) * (b - a)))
        (g (a + (t:ℂ) * (b - a)) * (b - a)) t := by
    intro t ht
    have hmemI : a + (t:ℂ) * (b - a) ∈ Metric.ball z₀ R := hmem ⟨ht.1.le, ht.2.le⟩
    have hFder := hF _ hmemI
    have hGs : HasDerivAt (fun s : ℂ => a + s * (b - a)) (b - a) (t:ℂ) := by
      have h1 := (hasDerivAt_id (t:ℂ)).mul_const (b - a)
      simp only [one_mul] at h1
      exact h1.const_add a
    exact (hFder.comp (t:ℂ) hGs).comp_ofReal
  have h_int : IntervalIntegrable (fun t : ℝ => g (a + (t:ℂ) * (b - a)) * (b - a))
      MeasureTheory.volume 0 1 := by
    have hFdiff : DifferentiableOn ℂ F (Metric.ball z₀ R) :=
      fun z hz => (hF z hz).differentiableAt.differentiableWithinAt
    have hFnhd : AnalyticOnNhd ℂ F (Metric.ball z₀ R) :=
      hFdiff.analyticOnNhd Metric.isOpen_ball
    have hgcont : ContinuousOn g (Metric.ball z₀ R) := by
      apply (hFnhd.deriv_of_isOpen Metric.isOpen_ball).continuousOn.congr
      intro z hz; exact (hF z hz).deriv.symm
    exact ((hgcont.comp
      (continuousOn_const.add
        (Complex.continuous_ofReal.continuousOn.mul continuousOn_const))
      hmem).mul continuousOn_const).intervalIntegrable_of_Icc (by norm_num)
  have h_ftc := intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le
    (a := 0) (b := 1) zero_le_one h_cont h_deriv h_int
  have h0 : a + ((0:ℝ):ℂ) * (b - a) = a := by push_cast; ring
  have h1 : a + ((1:ℝ):ℂ) * (b - a) = b := by push_cast; ring
  rw [h0, h1] at h_ftc
  exact h_ftc

/-- Per-cell Cauchy quadrilateral identity for the homotopy grid.

For each cell $(i, j)$, the four corners $BL = H(i/N, j/N)$, $BR = H((i+1)/N, j/N)$,
$TR = H((i+1)/N, (j+1)/N)$, $TL = H(i/N, (j+1)/N)$ all lie in
`Metric.ball (c i j) (r i j) ⊆ U`.  Since `g` is analytic on `U` and hence differentiable
on the ball, `cell_quad_identity_on_ball` yields the identity
(vertical-left integral − vertical-right integral) = (bottom integral − top integral). -/
theorem cell_quad_chord_vert_diff
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (_hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (_hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (_hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (_hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (_hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    ∀ i j : ℕ, i < N → j < N →
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
            * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
      -
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
            * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                - H (((i : ℝ) + 1) / N) ((j : ℝ) / N)))
      =
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N))
            * (H (((i : ℝ) + 1) / N) ((j : ℝ) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
      -
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
            * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                - H ((i : ℝ) / N) (((j : ℝ) + 1) / N))) := by
  intro i j hi hj
  obtain ⟨hr, hballU, hHcell⟩ := hgrid i j hi hj
  -- g is differentiable on the cell-ball (analytic on U ⊇ ball ⇒ differentiable on ball)
  have hgdiff : DifferentiableOn ℂ g (Metric.ball (c i j) (r i j)) :=
    (hg.mono hballU).differentiableOn
  -- four corners (BL, BR, TR, TL) live in the cell-ball
  have hN : (0 : ℝ) < (N : ℝ) := by exact_mod_cast hNpos
  have hi_le_i1 : (i : ℝ) / N ≤ ((i : ℝ) + 1) / N := by
    rw [div_le_div_iff_of_pos_right hN]; linarith
  have hj_le_j1 : (j : ℝ) / N ≤ ((j : ℝ) + 1) / N := by
    rw [div_le_div_iff_of_pos_right hN]; linarith
  have hmem_i_lo : ((i : ℝ) / N) ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) :=
    ⟨le_rfl, hi_le_i1⟩
  have hmem_i_hi : (((i : ℝ) + 1) / N) ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) :=
    ⟨hi_le_i1, le_rfl⟩
  have hmem_j_lo : ((j : ℝ) / N) ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N) :=
    ⟨le_rfl, hj_le_j1⟩
  have hmem_j_hi : (((j : ℝ) + 1) / N) ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N) :=
    ⟨hj_le_j1, le_rfl⟩
  have hBL : H ((i : ℝ) / N) ((j : ℝ) / N) ∈ Metric.ball (c i j) (r i j) :=
    hHcell _ hmem_i_lo _ hmem_j_lo
  have hBR : H (((i : ℝ) + 1) / N) ((j : ℝ) / N) ∈ Metric.ball (c i j) (r i j) :=
    hHcell _ hmem_i_hi _ hmem_j_lo
  have hTR : H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N) ∈ Metric.ball (c i j) (r i j) :=
    hHcell _ hmem_i_hi _ hmem_j_hi
  have hTL : H ((i : ℝ) / N) (((j : ℝ) + 1) / N) ∈ Metric.ball (c i j) (r i j) :=
    hHcell _ hmem_i_lo _ hmem_j_hi
  exact cell_quad_identity_on_ball hgdiff hBL hBR hTR hTL

/-- Row-strip homotopy invariance: for each row $i < N$, the column-chord sums at
$\tau = i/N$ and $\tau = (i+1)/N$ are equal.

Applies `cell_quad_chord_vert_diff` to each cell $(i, j)$ to write the difference of the
$j$-th chord integrals as $v(j) - v(j+1)$, where `v k` is the vertical chord integral at
column $k$.  Summing over `j ∈ Finset.range N` and telescoping via `Finset.sum_range_sub'`
gives zero, since both $v(0)$ and $v(N)$ vanish (as $H(\cdot, 0) = H(\cdot, 1) = \gamma(0)$
forces the integrand factor to zero). -/
theorem row_polygon_consec_eq
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    ∀ i : ℕ, i < N →
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
            * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
      =
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
            * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                - H (((i : ℝ) + 1) / N) ((j : ℝ) / N))) := by
  intro i hi
  have hiL : ((i : ℝ) / N) ∈ Set.Icc (0 : ℝ) 1 :=
    ⟨div_nonneg (Nat.cast_nonneg _) (Nat.cast_nonneg _),
     (div_le_one (by exact_mod_cast hNpos)).mpr (by exact_mod_cast Nat.le_of_lt hi)⟩
  have hiR : (((i : ℝ) + 1) / N) ∈ Set.Icc (0 : ℝ) 1 :=
    ⟨div_nonneg (by positivity) (Nat.cast_nonneg _),
     (div_le_one (by exact_mod_cast hNpos)).mpr (by exact_mod_cast Nat.succ_le_of_lt hi)⟩
  set v : ℕ → ℂ := fun k =>
    ∫ s in (0 : ℝ)..1,
      g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((k : ℝ) / N)
          + (s : ℂ) * H (((i : ℝ) + 1) / N) ((k : ℝ) / N))
        * (H (((i : ℝ) + 1) / N) ((k : ℝ) / N) - H ((i : ℝ) / N) ((k : ℝ) / N))
  have h_v0 : v 0 = 0 := by simp [v, hHleft _ hiL, hHleft _ hiR]
  have h_vN : v N = 0 := by
    have : (N : ℝ) / N = 1 := div_self (by exact_mod_cast hNpos.ne')
    simp [v, this, hHright _ hiL, hHright _ hiR]
  have h_cell_v : ∀ j : ℕ, j < N →
      (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
            * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
      - (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
            * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                - H (((i : ℝ) + 1) / N) ((j : ℝ) / N)))
      = v j - v (j + 1) := by
    intro j hj
    simp only [v]; push_cast
    convert cell_quad_chord_vert_diff hU hg hHcont hHleft hHright hHmaps N hNpos c r hgrid
        i j hi hj using 2
  exact sub_eq_zero.mp <| by
    rw [← Finset.sum_sub_distrib,
        Finset.sum_congr rfl (fun j hj => h_cell_v j (Finset.mem_range.mp hj)),
        Finset.sum_range_sub', h_v0, h_vN, sub_self]

/-- Telescoping induction over rows: if `h_step` equates consecutive row-polygon sums,
then the sum at $\tau = 0$ equals the sum at $\tau = 1$.

Proceeds by induction on $i \leq N$, applying `h_step` at each successor step, and
concludes by specialising to $i = N$ together with $(N : \mathbb{R})/N = 1$. -/
theorem row_polygon_telescope
    {g : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (N : ℕ) (hNpos : 0 < N)
    (h_step : ∀ i : ℕ, i < N →
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
            * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N)))
      =
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H (((i : ℝ) + 1) / N) ((j : ℝ) / N)
              + (s : ℂ) * H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N))
            * (H (((i : ℝ) + 1) / N) (((j : ℝ) + 1) / N)
                - H (((i : ℝ) + 1) / N) ((j : ℝ) / N)))) :
    ∑ j ∈ Finset.range N,
      (∫ s in (0 : ℝ)..1,
        g ((1 - (s : ℂ)) * H 0 ((j : ℝ) / N) + (s : ℂ) * H 0 (((j : ℝ) + 1) / N))
          * (H 0 (((j : ℝ) + 1) / N) - H 0 ((j : ℝ) / N)))
    =
    ∑ j ∈ Finset.range N,
      (∫ s in (0 : ℝ)..1,
        g ((1 - (s : ℂ)) * H 1 ((j : ℝ) / N) + (s : ℂ) * H 1 (((j : ℝ) + 1) / N))
          * (H 1 (((j : ℝ) + 1) / N) - H 1 ((j : ℝ) / N))) := by
  -- Prove by induction: sum at row 0 = sum at row i/N for each i ≤ N, then specialize to i=N.
  suffices key : ∀ i : ℕ, i ≤ N →
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H 0 ((j : ℝ) / N) + (s : ℂ) * H 0 (((j : ℝ) + 1) / N))
            * (H 0 (((j : ℝ) + 1) / N) - H 0 ((j : ℝ) / N))) =
      ∑ j ∈ Finset.range N,
        (∫ s in (0 : ℝ)..1,
          g ((1 - (s : ℂ)) * H ((i : ℝ) / N) ((j : ℝ) / N)
              + (s : ℂ) * H ((i : ℝ) / N) (((j : ℝ) + 1) / N))
            * (H ((i : ℝ) / N) (((j : ℝ) + 1) / N) - H ((i : ℝ) / N) ((j : ℝ) / N))) by
    have hN : (N : ℝ) / N = 1 := div_self (Nat.cast_pos.mpr hNpos).ne'
    have hkey := key N le_rfl
    simp only [hN] at hkey
    exact hkey
  intro i hi
  induction i with
  | zero =>
    simp only [Nat.cast_zero, zero_div]
  | succ n ih =>
    have hn : n < N := Nat.lt_of_succ_le hi
    rw [ih (Nat.le_of_lt hn)]
    push_cast
    exact h_step n hn

/-- Row-polygon sums at $\tau = 0$ and $\tau = 1$ coincide.

Combines `row_polygon_consec_eq` (single-step row equality via Cauchy on each cell ball and
telescoping over $j$) with `row_polygon_telescope` (iteration from $i = 0$ to $i = N$,
bridging $\tau = 0$ with $\tau = N/N = 1$). -/
theorem row_polygon_zero_eq_one
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (_hclosed : γ 0 = γ 1)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (_hH0 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 0 t = γ t)
    (_hH1 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 1 t = γ 0)
    (hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * H 0 ((j : ℝ) / N) + (s:ℂ) * H 0 (((j : ℝ) + 1) / N))
          * (H 0 (((j : ℝ) + 1) / N) - H 0 ((j : ℝ) / N)))
    =
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * H 1 ((j : ℝ) / N) + (s:ℂ) * H 1 (((j : ℝ) + 1) / N))
          * (H 1 (((j : ℝ) + 1) / N) - H 1 ((j : ℝ) / N))) := by
  have h_step :=
    row_polygon_consec_eq (γ := γ) hU hg hHcont hHleft hHright hHmaps N hNpos c r hgrid
  exact row_polygon_telescope N hNpos h_step

/-- Rewrite the chord-polygon sum using the homotopy initial condition `H 0 = γ`.

Shows that the row-polygon sum at $\tau = 0$ equals the chord-polygon sum for `γ`,
by applying `hH0` to each summand via `Finset.sum_congr`. -/
theorem chord_polygon_eq_h_zero_row
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (_hU : IsOpen U)
    (_hg : AnalyticOn ℂ g U)
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (_hclosed : γ 0 = γ 1)
    (_hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hH0 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 0 t = γ t)
    (_hH1 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 1 t = γ 0)
    (_hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (_hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (_hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (_hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
          * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N)))
    =
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * H 0 ((j : ℝ) / N) + (s:ℂ) * H 0 (((j : ℝ) + 1) / N))
          * (H 0 (((j : ℝ) + 1) / N) - H 0 ((j : ℝ) / N))) := by
    apply Finset.sum_congr rfl
    intro j hj
    have hj_lt : j < N := Finset.mem_range.mp hj
    have hjN : (0 : ℝ) < N := Nat.cast_pos.mpr hNpos
    have hj1 : (j : ℝ) / N ∈ Set.Icc (0:ℝ) 1 := by
      refine ⟨by positivity, (div_le_one hjN).mpr ?_⟩
      exact_mod_cast Nat.le_of_lt hj_lt
    have hj2 : ((j : ℝ) + 1) / N ∈ Set.Icc (0:ℝ) 1 := by
      refine ⟨by positivity, (div_le_one hjN).mpr ?_⟩
      exact_mod_cast hj_lt
    rw [hH0 _ hj1, hH0 _ hj2]

/-- The row-polygon sum at $\tau = 1$ vanishes.

Since `hH1` asserts `H 1 t = γ 0` for all `t`, every integrand factor
`H 1 ((j+1)/N) - H 1 (j/N)` is zero, so each summand is zero by `mul_zero` and
`intervalIntegral.integral_zero`. -/
theorem row_polygon_one_eq_zero
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (_hU : IsOpen U)
    (_hg : AnalyticOn ℂ g U)
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (_hclosed : γ 0 = γ 1)
    (_hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (_hH0 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 0 t = γ t)
    (hH1 : ∀ t ∈ Set.Icc (0 : ℝ) 1, H 1 t = γ 0)
    (_hHleft : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 0 = γ 0)
    (_hHright : ∀ τ ∈ Set.Icc (0 : ℝ) 1, H τ 1 = γ 0)
    (_hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (_hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N),
          ∀ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N),
            H τ t ∈ Metric.ball (c i j) (r i j))) :
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * H 1 ((j : ℝ) / N) + (s:ℂ) * H 1 (((j : ℝ) + 1) / N))
          * (H 1 (((j : ℝ) + 1) / N) - H 1 ((j : ℝ) / N))) = 0 := by
  apply Finset.sum_eq_zero
  intro j hj
  have hjN : j < N := Finset.mem_range.mp hj
  have hj_mem : (j : ℝ) / N ∈ Set.Icc (0 : ℝ) 1 :=
    ⟨by positivity, by rw [div_le_one (by exact_mod_cast hNpos)]; exact_mod_cast hjN.le⟩
  have hj1_mem : ((j : ℝ) + 1) / N ∈ Set.Icc (0 : ℝ) 1 :=
    ⟨by positivity, by rw [div_le_one (by exact_mod_cast hNpos)]; exact_mod_cast hjN⟩
  have heq : H 1 (((j : ℝ) + 1) / N) - H 1 ((j : ℝ) / N) = 0 := by
    rw [hH1 _ hj1_mem, hH1 _ hj_mem, sub_self]
  simp_rw [heq, mul_zero, intervalIntegral.integral_zero]

/-- **Chord-polygon integral vanishes**: the discretised contour integral of `g` along `γ`
sums to zero.

Chains three lemmas: (A) `chord_polygon_eq_h_zero_row` substitutes `γ = H 0` to rewrite the
chord-polygon sum as a row-polygon sum at $\tau = 0$; (B) `row_polygon_zero_eq_one` applies
the homotopy invariance from $\tau = 0$ to $\tau = 1$ via the grid cells; (C)
`row_polygon_one_eq_zero` observes that the $\tau = 1$ row-polygon vanishes because
`H 1 ≡ γ 0` forces every integrand factor to zero. -/
theorem chord_polygon_int_zero
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
    ∑ j ∈ Finset.range N,
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
          * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N))) = 0 := by
  have hA := chord_polygon_eq_h_zero_row hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  have hB := row_polygon_zero_eq_one hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  have hC := row_polygon_one_eq_zero hU hg hγ hmaps hclosed hHcont
    hH0 hH1 hHleft hHright hHmaps N hNpos c r hgrid
  exact (hA.trans hB).trans hC

end Library.Analysis.ResidueTheorem.CellQuadIdentity
