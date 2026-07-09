import Mathlib

/-!
# Reparametrization invariance of path integrals

This file establishes that complex path integrals of the form
`∫ t in 0..1, Q (γ t) * deriv γ t` are invariant under smooth monotone
reparametrizations of the unit interval $[0,1]$ with flat endpoints.

## Main statements

- `smooth_reparam_hermite_monotone_exists` : the Hermite cubic $\phi(t) = 3t^2 - 2t^3$
  is a $C^1$ monotone reparametrization of $[0,1]$ with $\phi(0)=0$, $\phi(1)=1$, and
  $\phi'(0) = \phi'(1) = 0$.
- `reparam_compose_path_integral_invariant_monotone` : if $\phi : [0,1] \to [0,1]$ is a
  $C^1$ monotone reparametrization with flat endpoints, then the path integral of $Q$
  along $\gamma \circ \phi$ equals that along $\gamma$.
- `c1_path_smooth_reparam_flat_endpoints` : every $C^1$ path $\gamma$ on $[0,1]$
  admits a smooth reparametrization with the same endpoints, avoidance set, and path
  integral, but with zero boundary derivatives.

## Implementation notes

The standard chain rule requires `γ` to be differentiable at `φ(t)`, which fails when
`φ(t)` lies in `{0, 1}`. Monotonicity of `φ` forces `deriv φ t = 0` at any such
interior point via a Fermat extremum argument (`phi_deriv_zero_at_interior_boundary`).
The Lipschitz bound on `γ` (from `ContDiffOn` on a compact interval) then gives
`deriv (γ ∘ φ) t = 0 = (deriv φ t) • (deriv γ (φ t))`.
-/

open scoped Topology

namespace Library.Analysis.ResidueTheorem.PathReparamIntegral

/-- The Hermite cubic $\phi(t) = 3t^2 - 2t^3$ witnesses existence of a $C^1$ monotone
reparametrization of $[0,1]$: $\phi(0)=0$, $\phi(1)=1$, $\phi'(0)=\phi'(1)=0$,
$\phi([0,1]) \subseteq [0,1]$, and $\phi'(t) = 6t(1-t) \ge 0$ on $[0,1]$. -/
theorem smooth_reparam_hermite_monotone_exists :
    ∃ φ : ℝ → ℝ,
      ContDiff ℝ 1 φ ∧
      φ 0 = 0 ∧
      φ 1 = 1 ∧
      deriv φ 0 = 0 ∧
      deriv φ 1 = 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) := by
  have hderiv : ∀ t : ℝ,
      HasDerivAt (fun x : ℝ => 3 * x ^ 2 - 2 * x ^ 3) (6 * t - 6 * t ^ 2) t :=
    fun t => by
      have := ((hasDerivAt_pow 2 t).const_mul 3).sub ((hasDerivAt_pow 3 t).const_mul 2)
      convert this using 1; ring
  refine ⟨fun t => 3 * t ^ 2 - 2 * t ^ 3, by fun_prop, by norm_num, by norm_num, ?_, ?_, ?_, ?_⟩
  · rw [(hderiv 0).deriv]; norm_num
  · rw [(hderiv 1).deriv]; norm_num
  · intro t ht
    exact ⟨by nlinarith [ht.1, ht.2, sq_nonneg t],
           by nlinarith [ht.1, ht.2, sq_nonneg t, sq_nonneg (1 - t)]⟩
  · intro t ht
    rw [(hderiv t).deriv]
    nlinarith [ht.1, ht.2, sq_nonneg t]

/-- If $\phi$ maps `Icc 0 1` into itself and `φ t = 1` at an interior point `t ∈ Ioo 0 1`,
then `deriv φ t = 0` by the Fermat extremum theorem applied to the local maximum. -/
theorem phi_deriv_zero_at_interior_max_value
    {φ : ℝ → ℝ}
    (_hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (_hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (h1 : φ t = 1) :
    deriv φ t = 0 := by
  have hmax : IsLocalMax φ t := by
    apply Filter.Eventually.mono (Ioo_mem_nhds ht.1 ht.2)
    intro s hs
    have hs' : s ∈ Set.Icc (0 : ℝ) 1 := Set.Ioo_subset_Icc_self hs
    have : φ s ≤ 1 := (hφrange s hs').2
    linarith [h1.symm ▸ le_refl (φ t)]
  exact hmax.deriv_eq_zero

/-- If $\phi$ maps `Icc 0 1` into itself and `φ t = 0` at an interior point `t ∈ Ioo 0 1`,
then `deriv φ t = 0` by the Fermat extremum theorem applied to the local minimum. -/
theorem phi_deriv_zero_at_interior_min_value
    {φ : ℝ → ℝ}
    (_hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (_hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (h0 : φ t = 0) :
    deriv φ t = 0 := by
  apply IsLocalMin.deriv_eq_zero
  filter_upwards [Ioo_mem_nhds ht.1 ht.2] with s hs
  rw [h0]; exact (hφrange s (Set.Ioo_subset_Icc_self hs)).1

/-- If $\phi$ maps `Icc 0 1` into itself and `φ t ∈ {0, 1}` at an interior point
`t ∈ Ioo 0 1`, then `deriv φ t = 0`. The case `φ t = 0` uses the local minimum
argument and `φ t = 1` uses the local maximum argument, both via
`IsLocalMin/Max.deriv_eq_zero`. -/
theorem phi_deriv_zero_at_interior_boundary
    {φ : ℝ → ℝ}
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (hbnd : φ t = 0 ∨ φ t = 1) :
    deriv φ t = 0 := by
  rcases hbnd with h0 | h1
  · exact phi_deriv_zero_at_interior_min_value hφ hφrange hφmono ht h0
  · exact phi_deriv_zero_at_interior_max_value hφ hφrange hφmono ht h1

/-- If `f` is Lipschitz on `s`, `g` eventually maps into `s` near `t`, and
`HasDerivAt g 0 t`, then `HasDerivAt (f ∘ g) 0 t`. This avoids the requirement that
`f` be differentiable at `g t`. -/
theorem lipschitz_comp_has_deriv_zero
    {f : ℝ → ℂ} {g : ℝ → ℝ} {s : Set ℝ} {K : NNReal} {t : ℝ}
    (hf : LipschitzOnWith K f s)
    (hg_in : ∀ᶠ x in 𝓝 t, g x ∈ s)
    (hg_deriv : HasDerivAt g 0 t) :
    HasDerivAt (f ∘ g) 0 t := by
  rw [hasDerivAt_iff_isLittleO]
  simp only [smul_zero, sub_zero]
  have hgt : g t ∈ s := hg_in.self_of_nhds
  rw [hasDerivAt_iff_isLittleO] at hg_deriv
  simp only [smul_zero, sub_zero] at hg_deriv
  have hbig : (fun x => f (g x) - f (g t)) =O[𝓝 t] (fun x => g x - g t) := by
    apply Asymptotics.isBigO_iff.mpr
    refine ⟨K, ?_⟩
    filter_upwards [hg_in] with x hx
    have h := hf.dist_le_mul (g x) hx (g t) hgt
    simp only [dist_eq_norm] at h
    exact_mod_cast h
  exact hbig.trans_isLittleO hg_deriv

/-- When `φ t ∈ {0, 1}` for an interior `t ∈ Ioo 0 1`, the composition `γ ∘ φ` has
zero derivative at `t`. The proof combines:
- `phi_deriv_zero_at_interior_boundary`: monotonicity forces `deriv φ t = 0`;
- `(`:.exists_lipschitzOnWith one_ne_zero (convex_Icc 0 1) isCompact_Icc) `γ` is Lipschitz on `Icc 0 1`;
- `lipschitz_comp_has_deriv_zero`: a Lipschitz function composed with a map of zero
  derivative also has zero derivative. -/
theorem comp_deriv_zero_at_interior_boundary
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc (0 : ℝ) 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (hbnd : φ t = 0 ∨ φ t = 1) :
    deriv (γ ∘ φ) t = 0 := by
  have h_phi_deriv : deriv φ t = 0 :=
    phi_deriv_zero_at_interior_boundary hφ hφrange hφmono ht hbnd
  have h_phi_hasderiv : HasDerivAt φ 0 t := by
    have h := ((hφ.differentiable one_ne_zero).differentiableAt (x := t)).hasDerivAt
    rwa [h_phi_deriv] at h
  obtain ⟨K, hK⟩ := (hγ.exists_lipschitzOnWith one_ne_zero (convex_Icc 0 1) isCompact_Icc)
  have h_phi_eventually : ∀ᶠ s in 𝓝 t, φ s ∈ Set.Icc (0 : ℝ) 1 := by
    have hmem : Set.Ioo (0 : ℝ) 1 ∈ 𝓝 t := isOpen_Ioo.mem_nhds ht
    filter_upwards [hmem] with s hs
    exact hφrange s (Set.Ioo_subset_Icc_self hs)
  have h_comp_hasderiv : HasDerivAt (γ ∘ φ) 0 t :=
    lipschitz_comp_has_deriv_zero hK h_phi_eventually h_phi_hasderiv
  exact h_comp_hasderiv.deriv

/-- The chain rule `deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t)` holds when
`φ t ∈ {0, 1}` for an interior `t ∈ Ioo 0 1`, because both sides are zero:
`deriv φ t = 0` by `phi_deriv_zero_at_interior_boundary` and
`deriv (γ ∘ φ) t = 0` by `comp_deriv_zero_at_interior_boundary`. -/
theorem chain_rule_at_boundary_image
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc (0 : ℝ) 1))
    (hφ : ContDiff ℝ 1 φ)
    (_hφ0 : φ 0 = 0)
    (_hφ1 : φ 1 = 1)
    (_hφd0 : deriv φ 0 = 0)
    (_hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t)
    {t : ℝ} (ht : t ∈ Set.Ioo (0 : ℝ) 1)
    (hbnd : φ t = 0 ∨ φ t = 1) :
    deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t) := by
  have h_phi : deriv φ t = 0 :=
    phi_deriv_zero_at_interior_boundary hφ hφrange hφmono ht hbnd
  have h_comp : deriv (γ ∘ φ) t = 0 :=
    comp_deriv_zero_at_interior_boundary hγ hφ hφrange hφmono ht hbnd
  rw [h_phi, h_comp]; exact (zero_smul ℝ _).symm

/-- A path `γ` that is $C^1$ on `Icc 0 1` is differentiable at every interior point
`z ∈ Ioo 0 1`. -/
theorem gamma_diff_at_interior
    {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc (0 : ℝ) 1))
    {z : ℝ} (hz : z ∈ Set.Ioo (0 : ℝ) 1) :
    DifferentiableAt ℝ γ z :=
  (hγ.differentiableOn one_ne_zero).differentiableAt
    (Filter.mem_of_superset (isOpen_Ioo.mem_nhds hz) Set.Ioo_subset_Icc_self)

/-- Pointwise chain rule: for `t ∈ Ioo 0 1`,
`deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t)`.
When `φ t ∈ Ioo 0 1` this follows from the standard chain rule; when `φ t ∈ {0, 1}`
it follows from `chain_rule_at_boundary_image`. -/
theorem chain_rule_compose_reparam_pointwise_ioo
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    ∀ t ∈ Set.Ioo (0 : ℝ) 1,
      deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t) := by
  intro t ht
  have ht_icc : t ∈ Set.Icc (0 : ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hφt_icc : φ t ∈ Set.Icc (0 : ℝ) 1 := hφrange t ht_icc
  by_cases hφt_int : φ t ∈ Set.Ioo (0 : ℝ) 1
  · have hφdAt : HasDerivAt φ (deriv φ t) t :=
      hφ.differentiable_one.differentiableAt.hasDerivAt
    have h_gamma_diff_int : DifferentiableAt ℝ γ (φ t) :=
      gamma_diff_at_interior hγ hφt_int
    have hγdAt : HasDerivAt γ (deriv γ (φ t)) (φ t) := h_gamma_diff_int.hasDerivAt
    exact (hγdAt.scomp t hφdAt).deriv
  · have hbnd : φ t = 0 ∨ φ t = 1 := by
      rcases hφt_icc with ⟨h0, h1⟩
      rcases eq_or_lt_of_le h0 with h0 | h0
      · exact Or.inl h0.symm
      · rcases eq_or_lt_of_le h1 with h1 | h1
        · exact Or.inr h1
        · exact absurd ⟨h0, h1⟩ hφt_int
    exact chain_rule_at_boundary_image hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono ht hbnd

/-- Almost-everywhere chain rule: `deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t)` holds
for a.e. `t` in `uIoc 0 1`, deduced from the pointwise identity on `Ioo 0 1`. -/
theorem chain_rule_compose_reparam_ae
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    ∀ᵐ t ∂(MeasureTheory.volume.restrict (Set.uIoc (0 : ℝ) 1)),
      deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t) := by
  have hpw : ∀ t ∈ Set.Ioo (0 : ℝ) 1,
      deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t) :=
    chain_rule_compose_reparam_pointwise_ioo hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  rw [show Set.uIoc (0 : ℝ) 1 = Set.Ioc 0 1 from Set.uIoc_of_le zero_le_one,
      ← MeasureTheory.restrict_Ioo_eq_restrict_Ioc]
  refine (MeasureTheory.ae_restrict_iff' measurableSet_Ioo).2 ?_
  exact Filter.Eventually.of_forall hpw

/-- The integrand of the reparametrized path integral equals the smeared integrand:
`Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t = deriv φ t • (Q (γ (φ t)) * deriv γ (φ t))`
for a.e. `t`, obtained by substituting the a.e. chain rule and using `mul_smul_comm`. -/
theorem integrand_compose_eq_smul_ae
    {Q : ℂ → ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    ∀ᵐ t ∂(MeasureTheory.volume.restrict (Set.uIoc (0 : ℝ) 1)),
      Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t =
        deriv φ t • (Q (γ (φ t)) * deriv γ (φ t)) := by
  have h_chain := chain_rule_compose_reparam_ae hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  filter_upwards [h_chain] with t ht
  simp only [Function.comp_apply, ht, mul_smul_comm]

/-- The smeared integral `∫ t in 0..1, deriv φ t • (Q (γ (φ t)) * deriv γ (φ t))` equals
`∫ s in 0..1, Q (γ s) * deriv γ s`, via the monotone change-of-variables formula
`intervalIntegral.integral_deriv_smul_comp_of_deriv_nonneg`. -/
theorem integral_smul_compose_monotone_reparam
    {Q : ℂ → ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (_hφd0 : deriv φ 0 = 0)
    (_hφd1 : deriv φ 1 = 0)
    (_hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    (∫ t in (0 : ℝ)..1, deriv φ t • (Q (γ (φ t)) * deriv γ (φ t))) =
      ∫ s in (0 : ℝ)..1, Q (γ s) * deriv γ s := by
  have hφcont : ContinuousOn φ (Set.uIcc 0 1) := hφ.continuous.continuousOn
  have hφderiv : ∀ x ∈ Set.Ioo (min 0 1 : ℝ) (max 0 1), HasDerivAt φ (deriv φ x) x :=
    fun x _ => (hφ.differentiable (by norm_num)).differentiableAt.hasDerivAt
  have hφnonneg : ∀ x ∈ Set.Ioo (min 0 1 : ℝ) (max 0 1), 0 ≤ deriv φ x := by
    intro x hx
    simp only [min_def, max_def, if_pos (by norm_num : (0 : ℝ) ≤ 1)] at hx
    exact hφmono x (Set.Ioo_subset_Icc_self hx)
  have key := intervalIntegral.integral_deriv_smul_comp_of_deriv_nonneg
    (f := φ) (f' := deriv φ) (g := fun u => Q (γ u) * deriv γ u)
    (a := (0 : ℝ)) (b := 1)
    hφcont hφderiv hφnonneg
  simp only [Function.comp_apply] at key
  rw [hφ0, hφ1] at key
  exact key

/-- **Reparametrization invariance**: if `φ : ℝ → ℝ` is a $C^1$ monotone
reparametrization of `[0,1]` with `φ(0)=0`, `φ(1)=1`, and `φ'(0)=φ'(1)=0`, then
`∫ t in 0..1, Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t = ∫ t in 0..1, Q (γ t) * deriv γ t`.
The proof combines the a.e. chain-rule identity and the monotone change-of-variables
formula. -/
theorem reparam_compose_path_integral_invariant_monotone
    {Q : ℂ → ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    (∫ t in (0 : ℝ)..1, Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t) =
      (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t) := by
  have h_ae := integrand_compose_eq_smul_ae (Q := Q) (γ := γ) (φ := φ)
    hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  have h_cov := integral_smul_compose_monotone_reparam (Q := Q) (γ := γ) (φ := φ)
    hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  rw [intervalIntegral.integral_congr_ae_restrict h_ae]
  exact h_cov

/-- The composition `γ ∘ φ` satisfies `(γ ∘ φ) 1 = γ 1` when `φ 1 = 1`. -/
theorem gamma_circ_phi_at_one
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hφ1 : φ 1 = 1) :
    (γ ∘ φ) 1 = γ 1 := by simp_all only [Function.comp_apply]

/-- The composition `γ ∘ φ` satisfies `(γ ∘ φ) 0 = γ 0` when `φ 0 = 0`. -/
theorem gamma_circ_phi_at_zero
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hφ0 : φ 0 = 0) :
    (γ ∘ φ) 0 = γ 0 := by simp_all only [Function.comp_apply]

/-- If `γ` avoids `a` on `Icc 0 1` and `φ` maps `Icc 0 1` into itself, then
`γ ∘ φ` also avoids `a` on `Icc 0 1`. -/
theorem gamma_circ_phi_avoidance_unit
    {a : ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    ∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a := by
  simp_all only [Set.mem_Icc, ne_eq, and_imp, Function.comp_apply, not_false_eq_true,
    implies_true]

/-- If `γ` is $C^1$ on `Icc 0 1` and `φ` is $C^1$ with `φ(Icc 0 1) ⊆ Icc 0 1`,
then `γ ∘ φ` is $C^1$ on `Icc 0 1`. -/
theorem gamma_circ_phi_contdiffon_unit
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) :=
  hγ.comp hφ.contDiffOn (fun t ht => hφrange t ht)

/-- The within-derivative of `γ ∘ φ` at `0` is zero when `deriv φ 0 = 0`.
The proof builds `HasDerivWithinAt` for both `φ` and `γ` at the endpoint,
composes them via `HasDerivWithinAt.scomp`, then promotes to `derivWithin`
using `uniqueDiffOn_Icc`. -/
theorem gamma_circ_phi_derivwithin_zero_at_zero
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφd0 : deriv φ 0 = 0) :
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0 := by
  have hφ_at : HasDerivAt φ (deriv φ 0) 0 :=
    (hφ.differentiable one_ne_zero).differentiableAt.hasDerivAt
  rw [hφd0] at hφ_at
  have hφ_within : HasDerivWithinAt φ 0 (Set.Icc 0 1) 0 := hφ_at.hasDerivWithinAt
  have hφ0_mem : φ 0 ∈ Set.Icc (0 : ℝ) 1 := hφrange 0 (Set.left_mem_Icc.mpr zero_le_one)
  have hγ_diff : DifferentiableWithinAt ℝ γ (Set.Icc 0 1) (φ 0) :=
    hγ.differentiableOn one_ne_zero (φ 0) hφ0_mem
  have hγ_within :
      HasDerivWithinAt γ (derivWithin γ (Set.Icc 0 1) (φ 0)) (Set.Icc 0 1) (φ 0) :=
    hγ_diff.hasDerivWithinAt
  have h_maps : Set.MapsTo φ (Set.Icc 0 1) (Set.Icc 0 1) := hφrange
  have h_comp : HasDerivWithinAt (γ ∘ φ) ((0 : ℝ) • derivWithin γ (Set.Icc 0 1) (φ 0))
      (Set.Icc 0 1) 0 := hγ_within.scomp 0 hφ_within h_maps
  have h_zero : ((0 : ℝ) • derivWithin γ (Set.Icc 0 1) (φ 0) : ℂ) = 0 := by simp
  rw [h_zero] at h_comp
  exact h_comp.derivWithin
    ((uniqueDiffOn_Icc zero_lt_one) 0 (Set.left_mem_Icc.mpr zero_le_one))

/-- The within-derivative of `γ ∘ φ` at `1` equals
`derivWithin γ (Set.Icc 0 1) (φ 1) * derivWithin φ (Set.Icc 0 1) 1`,
by the chain rule for within-derivatives (`derivWithin.scomp`). -/
theorem derivwithin_gamma_comp_phi_chain_at_one
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 1
      = derivWithin γ (Set.Icc 0 1) (φ 1) * derivWithin φ (Set.Icc 0 1) 1 := by
  have hmem : (1 : ℝ) ∈ Set.Icc (0 : ℝ) 1 := Set.right_mem_Icc.mpr zero_le_one
  have hφ1mem : φ 1 ∈ Set.Icc (0 : ℝ) 1 := hφrange 1 hmem
  have hDγ : DifferentiableWithinAt ℝ γ (Set.Icc 0 1) (φ 1) :=
    hγ.differentiableOn one_ne_zero _ hφ1mem
  have hDφ : DifferentiableWithinAt ℝ φ (Set.Icc 0 1) 1 :=
    (hφ.differentiable one_ne_zero).differentiableAt.differentiableWithinAt
  have hMaps : Set.MapsTo φ (Set.Icc 0 1) (Set.Icc 0 1) := hφrange
  rw [derivWithin.scomp (1 : ℝ) hDγ hDφ hMaps]
  exact Complex.real_smul.trans (mul_comm _ _)

/-- The within-derivative of `φ` at `1` (relative to `Icc 0 1`) is zero when
`deriv φ 1 = 0`, because `φ` is differentiable everywhere. -/
theorem derivwithin_phi_eq_zero_at_one
    {φ : ℝ → ℝ} (hφ : ContDiff ℝ 1 φ) (hφd1 : deriv φ 1 = 0) :
    derivWithin φ (Set.Icc 0 1) 1 = 0 := by
  have hd : DifferentiableAt ℝ φ 1 := (hφ.differentiable one_ne_zero).differentiableAt
  rw [hd.derivWithin (uniqueDiffOn_Icc (by norm_num : (0 : ℝ) < 1) _
    (Set.right_mem_Icc.mpr (by norm_num : (0 : ℝ) ≤ 1)))]
  exact hφd1

/-- The within-derivative of `γ ∘ φ` at `1` is zero when `deriv φ 1 = 0`,
combining `derivwithin_gamma_comp_phi_chain_at_one` and `derivwithin_phi_eq_zero_at_one`. -/
theorem gamma_circ_phi_derivwithin_zero_at_one
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφd1 : deriv φ 1 = 0) :
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0 := by
  have hA : derivWithin φ (Set.Icc 0 1) 1 = 0 :=
    derivwithin_phi_eq_zero_at_one hφ hφd1
  have hB : derivWithin (γ ∘ φ) (Set.Icc 0 1) 1
      = derivWithin γ (Set.Icc 0 1) (φ 1) * derivWithin φ (Set.Icc 0 1) 1 :=
    derivwithin_gamma_comp_phi_chain_at_one hγ hφ hφrange
  rw [hB, hA]; simp

/-- Bundles the non-integral $C^1$ properties of the reparametrized path `γ ∘ φ`:
it is $C^1$ on `Icc 0 1`, matches `γ` at the endpoints, has zero boundary derivatives,
and avoids the puncture point `a`. -/
theorem reparam_compose_c1_path_props
    {a : ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) ∧
    (γ ∘ φ) 0 = γ 0 ∧
    (γ ∘ φ) 1 = γ 1 ∧
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0 ∧
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0 ∧
    (∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a) := by
  have h1 : ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) :=
    gamma_circ_phi_contdiffon_unit hγ hφ hφrange
  have h2 : (γ ∘ φ) 0 = γ 0 :=
    gamma_circ_phi_at_zero (γ := γ) hφ0
  have h3 : (γ ∘ φ) 1 = γ 1 :=
    gamma_circ_phi_at_one (γ := γ) hφ1
  have h4 : derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0 :=
    gamma_circ_phi_derivwithin_zero_at_zero hγ hφ hφrange hφd0
  have h5 : derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0 :=
    gamma_circ_phi_derivwithin_zero_at_one hγ hφ hφrange hφd1
  have h6 : ∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a :=
    gamma_circ_phi_avoidance_unit havoid hφrange
  exact ⟨h1, h2, h3, h4, h5, h6⟩

/-- **Smooth reparametrization with flat endpoints**: every $C^1$ path `γ` on `[0,1]`
that avoids `a` admits a reparametrization `γ' = γ ∘ φ` (via the Hermite cubic `φ`)
such that `γ'` is $C^1$, has the same endpoints and avoidance set as `γ`, satisfies
`derivWithin γ' _ 0 = 0` and `derivWithin γ' _ 1 = 0`, and has the same path integral
`∫ t in 0..1, Q (γ' t) * deriv γ' t`. -/
theorem c1_path_smooth_reparam_flat_endpoints
    {Q : ℂ → ℂ} {a : ℂ} {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∃ γ' : ℝ → ℂ,
      ContDiffOn ℝ 1 γ' (Set.Icc 0 1) ∧
      γ' 0 = γ 0 ∧
      γ' 1 = γ 1 ∧
      derivWithin γ' (Set.Icc 0 1) 0 = 0 ∧
      derivWithin γ' (Set.Icc 0 1) 1 = 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, γ' t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (γ' t) * deriv γ' t) =
        (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t) := by
  obtain ⟨φ, hφ, hφ0, hφ1, hφd0, hφd1, hφrange, hφmono⟩ := smooth_reparam_hermite_monotone_exists
  obtain ⟨hcomp, hcomp0, hcomp1, hcompd0, hcompd1, hcompav⟩ :=
    reparam_compose_c1_path_props hγ havoid hφ hφ0 hφ1 hφd0 hφd1 hφrange
  exact ⟨γ ∘ φ, hcomp, hcomp0, hcomp1, hcompd0, hcompd1, hcompav,
    reparam_compose_path_integral_invariant_monotone (Q := Q)
      hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono⟩

end Library.Analysis.ResidueTheorem.PathReparamIntegral
