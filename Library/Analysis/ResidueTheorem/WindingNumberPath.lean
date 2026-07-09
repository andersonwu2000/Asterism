import Library.Analysis.ResidueTheorem.WindingNumberFormula
import Library.Analysis.ResidueTheorem.WindingNumberInt

/-!
# Winding number path integral identities

This file establishes identities between path integrals of the form
$\int_0^1 \frac{\gamma'(t)}{w - \gamma(t)}\,dt$ and the winding number
`Complex.windingNumber γ w`, and proves that the winding number is constant on
small circles whose interiors are avoided by the path.

## Main statements

- `path_int_eq_neg_winding_at_pt`: the path integral
  $\int_0^1 \frac{\gamma'(t)}{z - \gamma(t)}\,dt$ equals
  $-(2\pi i) \cdot \mathrm{windingNumber}(\gamma, z)$ when $\gamma$ avoids $z$.
- `eps_bump_radius_avoiding_path`: by compactness, if $\gamma$ separates from $a$
  by more than $\varepsilon$, there exists $r > \varepsilon$ with the same property.
- `gamma_avoids_w_on_sphere`: if $\gamma$ separates from $a$ by more than $\varepsilon$,
  then $\gamma$ does not meet the $\varepsilon$-sphere `Metric.sphere a ε`.
- `winding_const_on_eps_sphere`: `Complex.windingNumber γ` is constant on
  `Metric.sphere a ε`, equal to `Complex.windingNumber γ a`.
- `path_int_eq_neg_winding_at_w`: the path integral formula holds for every point
  on `Metric.sphere a ε`.
-/

open Library.Analysis.ResidueTheorem.WindingNumberFormula
open Library.Analysis.ResidueTheorem.WindingNumberInt

namespace Library.Analysis.ResidueTheorem.WindingNumberPath

/-- For a closed $C^1$ path `γ` that avoids `z`, the path integral
$\int_0^1 \frac{\gamma'(t)}{z - \gamma(t)}\,dt$ equals
$-(2\pi i) \cdot \mathrm{windingNumber}(\gamma, z)$.

This is a sign-flipped reformulation of `winding_integral_formula`: the integrand
`deriv γ t / (z - γ t)` equals `-(deriv γ t / (γ t - z))` by `ring`, so the
negation factors out of the integral. -/
theorem path_int_eq_neg_winding_at_pt
    {γ : ℝ → ℂ} {z : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ z) :
    (∫ t in (0:ℝ)..1, deriv γ t / (z - γ t))
      = -(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ z : ℂ) := by
  have hform := winding_integral_formula hγ h_avoid hclosed
  have heq : ∀ t : ℝ, deriv γ t / (z - γ t) = -(deriv γ t / (γ t - z)) := fun t => by
    rw [show z - γ t = -(γ t - z) from by ring, div_neg]
  simp_rw [heq]
  rw [intervalIntegral.integral_neg, hform]
  ring

/-- If the image of a $C^1$ path `γ` on $[0,1]$ is separated from `a` by more than `ε`
(i.e., `dist (γ t) a > ε` for all `t`), then by compactness there exists `r > ε`
such that `dist (γ t) a > r` for all `t`. -/
theorem eps_bump_radius_avoiding_path
    {γ : ℝ → ℂ} {a : ℂ} {ε : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hε_pos : 0 < ε)
    (hε_sep : ∀ t ∈ Set.Icc (0 : ℝ) 1, ε < dist (γ t) a) :
    ∃ r : ℝ, ε < r ∧ ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) a := by
  have hγcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have hcont : ContinuousOn (fun t => dist (γ t) a) (Set.Icc 0 1) := by fun_prop
  have hne : (Set.Icc (0 : ℝ) 1).Nonempty := ⟨0, by norm_num⟩
  obtain ⟨t₀, ht₀_mem, ht₀_min⟩ := isCompact_Icc.exists_isMinOn hne hcont
  refine ⟨(ε + dist (γ t₀) a) / 2, by linarith [hε_sep t₀ ht₀_mem], ?_⟩
  intro t ht
  have hle : dist (γ t₀) a ≤ dist (γ t) a := ht₀_min ht
  linarith [hε_sep t₀ ht₀_mem]

/-- If `dist (γ t) a > ε` for all `t ∈ [0, 1]`, then `γ` avoids every point `w`
on the metric sphere `Metric.sphere a ε`. -/
theorem gamma_avoids_w_on_sphere
    {γ : ℝ → ℂ} {a : ℂ} {ε : ℝ}
    (hε_sep : ∀ t ∈ Set.Icc (0 : ℝ) 1, ε < dist (γ t) a) :
    ∀ w ∈ Metric.sphere a ε, ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ w := by
  intro w hw t ht heq
  rw [Metric.mem_sphere] at hw
  have h := hε_sep t ht
  rw [heq] at h
  linarith

/-- For a closed $C^1$ path `γ` whose image is separated from `a` by more than `ε`,
`Complex.windingNumber γ w = Complex.windingNumber γ a` for every `w` on the
$\varepsilon$-sphere `Metric.sphere a ε`.

The proof bumps `ε` to a strictly larger radius `r` via `eps_bump_radius_avoiding_path`
(using compactness of $[0,1]$), so that `w` lies in the open `r`-ball, and then
applies `winding_const_on_open_ball_off_image`. -/
theorem winding_const_on_eps_sphere
    {γ : ℝ → ℂ} {a : ℂ} {ε : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (hε_pos : 0 < ε)
    (hε_sep : ∀ t ∈ Set.Icc (0 : ℝ) 1, ε < dist (γ t) a) :
    ∀ w ∈ Metric.sphere a ε,
      Complex.windingNumber γ w = Complex.windingNumber γ a := by
  intro w hw
  obtain ⟨r, hr_gt, h_avoid_r⟩ :=
    eps_bump_radius_avoiding_path hγ hε_pos hε_sep
  have hr_pos : 0 < r := lt_trans hε_pos hr_gt
  have hw_dist : dist w a = ε := Metric.mem_sphere.mp hw
  have hw_in_ball : w ∈ Metric.ball a r := by
    rw [Metric.mem_ball]; exact hw_dist ▸ hr_gt
  exact winding_const_on_open_ball_off_image hγ hclosed hr_pos h_avoid_r w hw_in_ball

/-- For a closed $C^1$ path `γ` whose image is separated from `a` by more than `ε`,
the path integral $\int_0^1 \frac{\gamma'(t)}{w - \gamma(t)}\,dt$ equals
$-(2\pi i) \cdot \mathrm{windingNumber}(\gamma, w)$ for every `w ∈ Metric.sphere a ε`.

The proof uses `gamma_avoids_w_on_sphere` to ensure `γ` avoids `w`, then applies
`path_int_eq_neg_winding_at_pt`. -/
theorem path_int_eq_neg_winding_at_w
    {γ : ℝ → ℂ} {a : ℂ} {ε : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (hε_sep : ∀ t ∈ Set.Icc (0 : ℝ) 1, ε < dist (γ t) a) :
    ∀ w ∈ Metric.sphere a ε,
      (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t))
        = -(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ w : ℂ) := by
  intro w hw
  have h_avoid_w : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ w :=
    gamma_avoids_w_on_sphere (γ := γ) (a := a) (ε := ε) hε_sep w hw
  exact path_int_eq_neg_winding_at_pt hγ hclosed h_avoid_w

end Library.Analysis.ResidueTheorem.WindingNumberPath
