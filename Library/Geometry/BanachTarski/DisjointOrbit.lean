import Mathlib.Algebra.Group.Action.Equidecomp
import Mathlib.Analysis.Real.Cardinality
import Mathlib.Order.BourbakiWitt
import Mathlib.Order.CompletePartialOrder
import Library.Geometry.BanachTarski.CollisionAngles
import Library.Geometry.BanachTarski.Defs

/-!
# Disjoint orbit construction for the Banach–Tarski paradox

This file provides the rotation and orbit-disjointness lemmas used in the construction
of the Banach–Tarski paradox. The key result is
`exists_rotation_pairwise_disjoint_orbit_off_origin`: given a countable set $D$ not
containing the origin, there exists an isometry `ρ` fixing the origin whose iterates
produce pairwise disjoint images of $D$.

## Main statements

- `pairwise_disjoint_of_shift_disjoint`: if an isometry `g` satisfies
  `Disjoint ((g ^ n) '' D) D` for all positive `n`, then its iterates produce pairwise
  disjoint images of `D`.
- `bad_angles_countable`: the set of rotation angles causing collisions in a countable
  set `D` is itself countable.
- `good_angle_avoids_collisions`: a rotation angle avoiding all collisions in `D` exists.
- `exists_rotation_pairwise_disjoint_orbit_off_origin`: **main theorem** — for any
  countable set `D` not containing the origin, a pairwise-disjoint orbit rotation exists.

## Implementation notes

The proofs use a Hilbert-hotel / uncountability argument: the set of "bad" angles is a
countable union of countable sets (hence countable), while `ℝ` is uncountable, so a good
angle must exist. The z-axis avoidance step is handled separately before choosing the
main rotation angle.
-/

open Library.Geometry.BanachTarski.CollisionAngles
open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.DisjointOrbit

/-- If `g ^ n` shifts `D` off itself for every positive `n` (i.e.,
`Disjoint ((g ^ n) '' D) D`), then the family of images `(g ^ i) '' D` is pairwise
disjoint. The proof uses `wlog i < j`, writes `j = i + n`, and cancels the injective
`g ^ i` via `Set.disjoint_image_iff`. -/
theorem pairwise_disjoint_of_shift_disjoint (g : E ≃ᵢ E) (D : Set E)
    (h : ∀ n : ℕ, 1 ≤ n → Disjoint ((g ^ n) '' D) D) :
    Pairwise (fun i j : ℕ => Disjoint ((g ^ i) '' D) ((g ^ j) '' D)) := by
  intro i j hij
  wlog hlt : i < j generalizing i j
  · have hji : j < i := (not_lt.mp hlt).lt_of_ne (Ne.symm hij)
    exact (this (Ne.symm hij) hji).symm
  set n := j - i with hn
  have hjn : j = i + n := by omega
  have h1n : 1 ≤ n := by omega
  have hcomp : (g ^ j) '' D = (g ^ i) '' ((g ^ n) '' D) := by
    rw [hjn, pow_add, ← Set.image_comp]
    rfl
  rw [hcomp, Set.disjoint_image_iff (g ^ i).injective]
  exact (h n h1n).symm

/-- If pairwise collision sets `{θ | R θ p = q}` are countable for all `p q ∈ D`,
then so are the scaled sets `{θ | R (n * θ) p = q}` for any positive natural `n`.
The proof bijects via the map `φ ↦ φ / n`. -/
theorem scaled_collision_countable (D : Set E) (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    ∀ (n : ℕ), 1 ≤ n → ∀ p ∈ D, ∀ q ∈ D,
      {θ : ℝ | R ((n : ℝ) * θ) p = q}.Countable := by
  intro n hn p hp q hq
  have hn_pos : (n : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (by omega)
  have heq : {θ : ℝ | R ((n : ℝ) * θ) p = q} =
      (fun φ => φ / (n : ℝ)) '' {φ : ℝ | R φ p = q} := by
    ext θ
    simp only [Set.mem_setOf_eq, Set.mem_image]
    constructor
    · intro h
      exact ⟨(n : ℝ) * θ, h, by field_simp⟩
    · rintro ⟨φ, hφ, rfl⟩
      rwa [mul_div_cancel₀ φ hn_pos]
  rw [heq]
  exact (hcol p hp q hq).image _

/-- The set of angles `θ` for which `R (n * θ)` maps some point of `D` to another point
of `D` (for some positive `n`) is countable, provided `D` is countable and each single
collision set `{θ | R θ p = q}` is countable. -/
theorem bad_angles_countable (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}.Countable := by
  have hscaled := scaled_collision_countable D R hcol
  have key : {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}
      = ⋃ (n : ℕ), {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} := by
    ext θ; simp only [Set.mem_setOf_eq, Set.mem_iUnion]
  rw [key]
  apply Set.countable_iUnion
  intro n
  by_cases hn : 1 ≤ n
  · have : {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}
        = ⋃ p ∈ D, ⋃ q ∈ D, {θ : ℝ | R ((n : ℝ) * θ) p = q} := by
      ext θ; simp only [Set.mem_setOf_eq, Set.mem_iUnion, hn, true_and]; tauto
    rw [this]
    exact hD.biUnion (fun p hp => hD.biUnion (fun q hq => hscaled n hn p hp q hq))
  · have : {θ : ℝ | 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} = ∅ := by
      ext θ; simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false, not_and]
      intro h; exact absurd h hn
    rw [this]; exact Set.countable_empty

/-- Given a one-parameter family `R` of isometries with `R θ 0 = 0` and
`(R θ) ^ n = R (n * θ)`, and a countable set `D` with countable collision sets, there
exists a rotation `ρ = R θ` fixing the origin such that `(ρ ^ n) '' D` is disjoint from
`D` for every positive `n`. The angle `θ` is chosen outside the countable bad set. -/
theorem good_angle_avoids_collisions (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (h0 : ∀ θ : ℝ, R θ 0 = 0)
    (hpow : ∀ (θ : ℝ) (n : ℕ), (R θ) ^ n = R ((n : ℝ) * θ))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧ ∀ n : ℕ, 1 ≤ n → Disjoint ((ρ ^ n) '' D) D := by
  have hB : {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}.Countable :=
    bad_angles_countable D hD R hcol
  obtain ⟨θ, hθ⟩ : ∃ θ : ℝ,
      θ ∉ {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} := by
    by_contra h
    push Not at h
    exact Cardinal.not_countable_real (by rwa [Set.eq_univ_of_forall h] at hB)
  refine ⟨R θ, h0 θ, ?_⟩
  intro n hn
  rw [Set.disjoint_left]
  rintro x ⟨p, hp, rfl⟩ hx
  exact hθ ⟨n, hn, p, hp, (R θ ^ n) p, hx, by rw [hpow]⟩

/-- The set of angles `θ` for which some point of `D` maps onto the z-axis
(i.e., coordinates 0 and 1 are both zero) is countable, provided `D` is countable and
each per-point landing set is countable. -/
theorem zaxis_bad_angles_countable (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, {θ : ℝ | (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable) :
    {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable := by
  have heq : {θ : ℝ | ∃ p ∈ D, ((R θ) p).ofLp 0 = 0 ∧ ((R θ) p).ofLp 1 = 0} =
      ⋃ p ∈ D, {θ : ℝ | ((R θ) p).ofLp 0 = 0 ∧ ((R θ) p).ofLp 1 = 0} := by
    ext θ
    simp only [Set.mem_setOf_eq, Set.mem_iUnion, exists_prop]
  rw [heq]
  exact hD.biUnion hcol

/-- Hilbert-hotel z-axis angle choice. Given a countable set `D` and a family `R` of
isometries whose per-point z-axis landing sets are countable, there exists an angle `θ`
such that no point of `D` is mapped onto the z-axis by `R θ`. The bad set
`{θ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}` is countable
(by `zaxis_bad_angles_countable`), and `ℝ` is uncountable, so a good angle exists. -/
theorem good_angle_avoids_zaxis
    (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, {θ : ℝ | (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable) :
    ∃ θ : ℝ, ∀ p ∈ D, ¬ ((R θ p) 0 = 0 ∧ (R θ p) 1 = 0) := by
  have hB : {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable :=
    zaxis_bad_angles_countable D hD R hcol
  obtain ⟨θ, hθ⟩ : ∃ θ : ℝ,
      θ ∉ {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0} := by
    by_contra h
    push Not at h
    exact Cardinal.not_countable_real (by rwa [Set.eq_univ_of_forall h] at hB)
  refine ⟨θ, ?_⟩
  intro p hp hcontra
  exact hθ ⟨p, hp, hcontra.1, hcontra.2⟩

/-- Conjugation transports pairwise-disjoint orbits: if `(ρ₀ ^ i) '' (g '' D)` is
pairwise disjoint, then so is `((g⁻¹ * ρ₀ * g) ^ i) '' D`. This uses the conjugation
identity `(g⁻¹ * ρ₀ * g) ^ n = g⁻¹ * ρ₀ ^ n * g` (`conj_pow`) to rewrite each image
as `g⁻¹ '' (ρ₀ ^ n '' (g '' D))`, then transfers disjointness across the injective `g⁻¹`
via `Set.disjoint_image_iff`. -/
theorem conj_pairwise_transport (g rho0 : E ≃ᵢ E) (D : Set E)
    (h : Pairwise (fun i j : ℕ =>
      Disjoint ((rho0 ^ i) '' (g '' D)) ((rho0 ^ j) '' (g '' D)))) :
    Pairwise (fun i j : ℕ =>
      Disjoint (((g⁻¹ * rho0 * g) ^ i) '' D) (((g⁻¹ * rho0 * g) ^ j) '' D)) := by
  have key : ∀ n : ℕ, ((g⁻¹ * rho0 * g) ^ n) '' D = ⇑g⁻¹ '' ((rho0 ^ n) '' (g '' D)) := by
    intro n
    have hconj : (g⁻¹ * rho0 * g) ^ n = g⁻¹ * rho0 ^ n * g := by
      have : g⁻¹ * rho0 * g = g⁻¹ * rho0 * (g⁻¹)⁻¹ := by rw [inv_inv]
      rw [this, conj_pow, inv_inv]
    rw [hconj]
    simp [Set.image_image, mul_assoc]
  intro i j hij
  rw [key i, key j]
  exact (Set.disjoint_image_iff g⁻¹.injective).mpr (h hij)

/-- Disjointness of sources transfers through preimage under `h`: if `f.source` and
`g.source` are disjoint, then `h.source ∩ h ⁻¹' f.source` and
`h.source ∩ h ⁻¹' g.source` are disjoint. -/
theorem transfer_disjoint (h f g : Equidecomp E (E ≃ᵢ E))
    (hdisj : Disjoint f.source g.source) :
    Disjoint (h.source ∩ h ⁻¹' f.source) (h.source ∩ h ⁻¹' g.source) := by
  exact (hdisj.preimage h).mono Set.inter_subset_right Set.inter_subset_right

/-- The source of the composed equidecomposition `h.trans (p.trans h.symm)` equals
`h.source ∩ h ⁻¹' p.source`, provided `p.target = h.target`. -/
theorem transfer_source (h p : Equidecomp E (E ≃ᵢ E)) (hpt : p.target = h.target) :
    (h.trans (p.trans h.symm)).source = h.source ∩ h ⁻¹' p.source := by
  simp only [Equidecomp.trans_toPartialEquiv, Equidecomp.symm_toPartialEquiv,
             PartialEquiv.trans_source, PartialEquiv.symm_source, ← hpt]
  ext x
  simp only [Set.mem_inter_iff, Set.mem_preimage]
  constructor
  · rintro ⟨hx_src, hx_h, _⟩
    exact ⟨hx_src, hx_h⟩
  · rintro ⟨hx_src, hx_h⟩
    exact ⟨hx_src, hx_h, p.map_source' hx_h⟩

/-- The preimage pieces of `h` over a partition `f.source ∪ g.source = B` of `h.target`
cover the source: `(h.source ∩ h ⁻¹' f.source) ∪ (h.source ∩ h ⁻¹' g.source) = A`,
given `h.source = A` and `h.target = B`. -/
theorem transfer_union (A B : Set E) (h f g : Equidecomp E (E ≃ᵢ E))
    (hsrc : h.source = A) (htgt : h.target = B) (hunion : f.source ∪ g.source = B) :
    (h.source ∩ h ⁻¹' f.source) ∪ (h.source ∩ h ⁻¹' g.source) = A := by
  rw [← Set.inter_union_distrib_left, ← Set.preimage_union, hunion, ← htgt]
  ext x
  simp only [Set.mem_inter_iff, Set.mem_preimage]
  constructor
  · rintro ⟨hx, _⟩; rwa [hsrc] at hx
  · intro hx
    rw [← hsrc] at hx
    exact ⟨hx, h.map_source' hx⟩

/-- The target of the composed equidecomposition `h.trans (p.trans h.symm)` equals
`h.source`, provided `p.target = h.target` and `p.source ⊆ h.target`. -/
theorem transfer_target (h p : Equidecomp E (E ≃ᵢ E))
    (hpt : p.target = h.target) (hps : p.source ⊆ h.target) :
    (h.trans (p.trans h.symm)).target = h.source := by aesop

/-- **Main theorem**: for any countable set `D ⊆ E` not containing the origin, there
exists an isometry `ρ : E ≃ᵢ E` fixing the origin such that the family of images
`(ρ ^ i) '' D` is pairwise disjoint.

The proof first chooses a z-axis-avoiding isometry `g = Q φ` (using
`good_angle_avoids_zaxis`), then applies `good_angle_avoids_collisions` to the image
`g '' D` (which is off-axis, so the off-axis rotation family `R₀` has countable
collision sets), and finally conjugates `ρ₀` by `g` to obtain `ρ = g⁻¹ * ρ₀ * g`. -/
theorem exists_rotation_pairwise_disjoint_orbit_off_origin
    (D : Set E) (hD : D.Countable) (hD0 : (0 : E) ∉ D) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧
      Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D)) := by
  obtain ⟨R₀, h0₀, hpow₀, hcol₀⟩ := zrotation_offaxis_collision_family
  obtain ⟨Q, hQ0, hQcol⟩ := zaxis_collision_angles_per_point_countable
  obtain ⟨φ, hφ⟩ := good_angle_avoids_zaxis D hD Q
    (fun p hp => hQcol p (by rintro rfl; exact hD0 hp))
  set g : E ≃ᵢ E := Q φ with hg
  have hg0 : g 0 = 0 := hQ0 φ
  have hgoff : ∀ p ∈ D, ¬ ((g p) 0 = 0 ∧ (g p) 1 = 0) := hφ
  have hcolR0 : ∀ p ∈ g '' D, ∀ q ∈ g '' D, {t : ℝ | R₀ t p = q}.Countable := by
    rintro p ⟨p₀, hp₀, rfl⟩ q _
    exact hcol₀ (g p₀) (hgoff p₀ hp₀) q
  obtain ⟨ρ₀, hρ₀0, hshift⟩ :=
    good_angle_avoids_collisions (g '' D) (hD.image g) R₀ h0₀ hpow₀ hcolR0
  have hpair : Pairwise (fun i j : ℕ =>
      Disjoint ((ρ₀ ^ i) '' (g '' D)) ((ρ₀ ^ j) '' (g '' D))) :=
    pairwise_disjoint_of_shift_disjoint ρ₀ (g '' D) hshift
  refine ⟨g⁻¹ * ρ₀ * g, ?_, conj_pairwise_transport g ρ₀ D hpair⟩
  have e1 : (g⁻¹ * ρ₀ * g) 0 = g⁻¹ (ρ₀ (g 0)) := rfl
  rw [e1, hg0, hρ₀0]
  exact (IsometryEquiv.symm_apply_eq g).mpr hg0.symm

end Library.Geometry.BanachTarski.DisjointOrbit
