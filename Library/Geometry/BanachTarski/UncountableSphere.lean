import Mathlib.Analysis.Normed.Module.Connected
import Mathlib.Analysis.Real.Cardinality
import Mathlib.GroupTheory.FreeGroup.CyclicallyReduced
import Library.Geometry.BanachTarski.Defs
import Library.Geometry.BanachTarski.FixedSetLemmas
import Library.Geometry.BanachTarski.SO3Embedding

open Library.Geometry.BanachTarski.Defs
open Library.Geometry.BanachTarski.FixedSetLemmas
open Library.Geometry.BanachTarski.SO3Embedding

/-!
# Uncountability of the sphere and irrational rotations

This file establishes that the radius-1/2 sphere in $\mathbb{R}^3$ is uncountable and that
there exists a rotation (a linear isometric equivalence of determinant 1) together with a
point on that sphere not fixed by any positive power of the rotation.

The argument proceeds in several steps.
- A closed real interval with two distinct endpoints has continuum-many points
  (`uicc_uncountable`).
- A preconnected metric space containing two distinct points is uncountable
  (`preconnected_two_points_uncountable`).
- The radius-1/2 sphere in `E` (i.e., $\mathbb{R}^3$ with the standard inner product) is
  preconnected and contains two explicit antipodal points, hence is uncountable
  (`half_sphere_uncountable`).
- For any non-trivial special-orthogonal transformation, each positive power fixes only
  finitely many points on the sphere (`fixed_set_half_sphere_finite`).
- The free SO(3) embedding (`free_so3_embedding`) supplies an infinite-order rotation whose
  powers collectively fix only countably many sphere points, leaving a point free of all
  powers (`exists_small_irrational_rotation`).

## Main statements

- `half_sphere_uncountable`: the metric sphere of radius $1/2$ in `E` is not countable.
- `exists_small_irrational_rotation`: there exist `R : E ≃ₗᵢ[ℝ] E` and `c : E` with
  `‖c‖ ≤ 1 / 2` such that `(R ^ n) c ≠ c` for all `n ≥ 1`.
-/

namespace Library.Geometry.BanachTarski.UncountableSphere

/-- The closed interval `Set.uIcc a b` in `ℝ` is not countable when `a ≠ b`.
This follows from `Cardinal.mk_Icc_real`: the interval has cardinality `Cardinal.continuum`,
which strictly exceeds `Cardinal.aleph0`. -/
theorem uicc_uncountable (a b : ℝ) (hab : a ≠ b) : ¬ (Set.uIcc a b).Countable := by
  intro h
  have hlt : a ⊓ b < a ⊔ b := inf_lt_sup.mpr hab
  have hmk : Cardinal.mk ↑(Set.Icc (a ⊓ b) (a ⊔ b)) = Cardinal.continuum :=
    Cardinal.mk_Icc_real hlt
  have hcount : Cardinal.mk ↑(Set.Icc (a ⊓ b) (a ⊔ b)) ≤ Cardinal.aleph0 :=
    Cardinal.mk_le_aleph0_iff.mpr h
  exact absurd (hmk ▸ hcount) (not_le.mpr Cardinal.aleph0_lt_continuum)

/-- A preconnected subset of `ℝ` containing two distinct points `a` and `b` is not countable.
The interval `Set.uIcc a b` is contained in `T` by `IsPreconnected.ordConnected`, and that
interval is uncountable by `uicc_uncountable`. -/
theorem preconnected_real_two_points_uncountable (T : Set ℝ) (hT : IsPreconnected T)
    (a b : ℝ) (ha : a ∈ T) (hb : b ∈ T) (hab : a ≠ b) : ¬ T.Countable := by
  intro hc
  have h_subset : Set.uIcc a b ⊆ T := hT.ordConnected.uIcc_subset ha hb
  have h_unc : ¬ (Set.uIcc a b).Countable := uicc_uncountable a b hab
  exact h_unc (hc.mono h_subset)

/-- A preconnected subset `S` of a metric space containing two distinct points is not countable.
The distance function `dist · p` maps `S` continuously into `ℝ`, producing a preconnected image
that contains both `0` and `dist q p` (which are distinct since `p ≠ q`). The result then
follows from `preconnected_real_two_points_uncountable`. -/
theorem preconnected_two_points_uncountable {X : Type*} [MetricSpace X] {S : Set X}
    {p q : X} (h : IsPreconnected S) (hp : p ∈ S) (hq : q ∈ S) (hpq : p ≠ q) :
    ¬ S.Countable := by
  intro hc
  have hcont : Continuous (fun x => dist x p) := by fun_prop
  have hT : IsPreconnected ((fun x => dist x p) '' S) := h.image _ hcont.continuousOn
  have hcountT : ((fun x => dist x p) '' S).Countable := hc.image _
  have ha : (0:ℝ) ∈ (fun x => dist x p) '' S := ⟨p, hp, by simp⟩
  have hb : dist q p ∈ (fun x => dist x p) '' S := ⟨q, hq, rfl⟩
  have hab : (0:ℝ) ≠ dist q p := by
    simp only [ne_eq, eq_comm (a := (0:ℝ)), dist_eq_zero]
    exact fun h => hpq h.symm
  exact preconnected_real_two_points_uncountable _ hT 0 (dist q p) ha hb hab hcountT

/-- The metric sphere of radius $1/2$ in `E` contains two distinct points.
The witnesses are `EuclideanSpace.single 0 (1/2)` and `EuclideanSpace.single 0 (-1/2)`,
whose norms are verified by `simp` and whose distinctness follows by comparing their
0th coordinate. -/
theorem half_sphere_two_distinct :
    ∃ p q : E, p ∈ Metric.sphere (0 : E) (1 / 2) ∧
      q ∈ Metric.sphere (0 : E) (1 / 2) ∧ p ≠ q := by
  refine ⟨EuclideanSpace.single (0 : Fin 3) (1/2 : ℝ),
          EuclideanSpace.single (0 : Fin 3) (-1/2 : ℝ), ?_, ?_, ?_⟩
  · simp
  · simp
  · intro h
    have h0 : (EuclideanSpace.single (0 : Fin 3) (1/2 : ℝ)).ofLp (0 : Fin 3) =
              (EuclideanSpace.single (0 : Fin 3) (-1/2 : ℝ)).ofLp (0 : Fin 3) :=
      congr_arg (fun x => x.ofLp 0) h
    simp at h0
    norm_num at h0

/-- The metric sphere of radius $1/2$ in `E` is not countable.
It is preconnected because `Module.rank ℝ E = 3 > 1` (so `isConnected_sphere` applies), and
it contains two distinct points by `half_sphere_two_distinct`; the conclusion follows from
`preconnected_two_points_uncountable`. -/
theorem half_sphere_uncountable : ¬ (Metric.sphere (0 : E) (1 / 2)).Countable := by
  have hrank : (1 : Cardinal) < Module.rank ℝ E := by
    have h3 : Module.rank ℝ E = 3 := by
      rw [← Module.finrank_eq_rank]; simp [E]
    rw [h3]; norm_num
  have hpre : IsPreconnected (Metric.sphere (0 : E) (1 / 2)) :=
    (isConnected_sphere hrank 0 (by norm_num)).isPreconnected
  obtain ⟨p, q, hp, hq, hpq⟩ := half_sphere_two_distinct
  exact preconnected_two_points_uncountable hpre hp hq hpq

/-- For a non-trivial special-orthogonal transformation `R`, the fixed-point set
`{x ∈ Metric.sphere (0 : E) (1 / 2) | R x = x}` is finite.
The scaling map `x ↦ 2 • x` injects the half-sphere fixed set into the radius-1 fixed set,
which is finite by `rotation_fixed_set_on_sphere_finite`. -/
theorem fixed_set_half_sphere_finite : ∀ (R : E ≃ₗᵢ[ℝ] E),
    LinearMap.det (R.toLinearEquiv.toLinearMap) = 1 → R ≠ LinearIsometryEquiv.refl ℝ E →
    {x ∈ Metric.sphere (0 : E) (1 / 2) | R x = x}.Finite := by
  intro R hdet hT
  have hfull := rotation_fixed_set_on_sphere_finite R hdet hT
  apply Set.Finite.of_finite_image (f := fun x => (2 : ℝ) • x)
  · apply hfull.subset
    rintro y ⟨x, ⟨hx_sph, hx_fix⟩, rfl⟩
    simp only [Set.mem_setOf_eq, Metric.mem_sphere, dist_eq_norm, sub_zero] at hx_sph ⊢
    refine ⟨?_, ?_⟩
    · rw [norm_smul, Real.norm_eq_abs, hx_sph]; norm_num
    · rw [map_smul, hx_fix]
  · intro a _ b _ hab
    exact smul_right_injective E (by norm_num) hab

/-- The union over all `n : ℕ` of the fixed-point sets of `R ^ (n + 1)` on the radius-1/2
sphere is countable, provided each such fixed-point set is finite. -/
theorem fixed_union_countable (R : E ≃ₗᵢ[ℝ] E)
    (hfin : ∀ n : ℕ, 1 ≤ n → {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ n) x = x}.Finite) :
    (⋃ n : ℕ, {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ (n + 1)) x = x}).Countable := by
  apply Set.countable_iUnion
  intro n
  exact (hfin (n + 1) (Nat.succ_pos n)).countable

/-- If the radius-1/2 sphere is uncountable and each fixed-point set of `R ^ n` (for `n ≥ 1`)
is finite, then there exists a point `c` with `‖c‖ ≤ 1 / 2` not fixed by any positive power of
`R`. -/
theorem exists_not_fixed_in_uncountable_sphere : ∀ (R : E ≃ₗᵢ[ℝ] E),
    ¬ (Metric.sphere (0 : E) (1 / 2)).Countable →
    (∀ n : ℕ, 1 ≤ n → {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ n) x = x}.Finite) →
    ∃ c, ‖c‖ ≤ 1 / 2 ∧ ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c := by
  intro R hunc hfin
  have hBc : (⋃ n : ℕ, {x ∈ Metric.sphere (0:E) (1/2) | (R ^ (n+1)) x = x}).Countable :=
    fixed_union_countable R hfin
  have hns : ¬ (Metric.sphere (0:E) (1/2)) ⊆
      (⋃ n : ℕ, {x ∈ Metric.sphere (0:E) (1/2) | (R ^ (n+1)) x = x}) :=
    fun h => hunc (hBc.mono h)
  rw [Set.not_subset] at hns
  obtain ⟨c, hcs, hcB⟩ := hns
  have hnorm : ‖c‖ = 1/2 := mem_sphere_zero_iff_norm.mp hcs
  refine ⟨c, le_of_eq hnorm, ?_⟩
  intro n hn heq
  apply hcB
  obtain ⟨m, rfl⟩ := Nat.exists_eq_succ_of_ne_zero (by omega : n ≠ 0)
  exact Set.mem_iUnion.mpr ⟨m, hcs, heq⟩

/-- Every positive power of the canonical generator `FreeGroup.of (0 : Fin 2)` is non-trivial
in the free group `FreeGroup (Fin 2)`. -/
theorem of_pow_ne_one : ∀ n : ℕ, 1 ≤ n → (FreeGroup.of (0 : Fin 2)) ^ n ≠ 1 := by aesop

/-- **Irrational rotation**: there exist a linear isometric equivalence `R : E ≃ₗᵢ[ℝ] E` and a
point `c : E` with `‖c‖ ≤ 1 / 2` such that `(R ^ n) c ≠ c` for every `n ≥ 1`.

The rotation `R` is taken to be `ψ (FreeGroup.of 0)`, a generator of the free SO(3) embedding
`ψ` from `free_so3_embedding`. Since every positive power of `FreeGroup.of 0` is non-trivial
(`of_pow_ne_one`), each `R ^ n` is a non-trivial special-orthogonal map, so its fixed set on the
radius-1/2 sphere is finite (`fixed_set_half_sphere_finite`). The union of these finite fixed
sets is countable, but the sphere itself is uncountable (`half_sphere_uncountable`), so a point
`c` escaping every fixed set exists by `exists_not_fixed_in_uncountable_sphere`. -/
theorem exists_small_irrational_rotation :
    ∃ (R : E ≃ₗᵢ[ℝ] E) (c : E),
      ‖c‖ ≤ 1 / 2 ∧ ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c := by
  obtain ⟨ψ, hinj, hprop⟩ := free_so3_embedding
  have hfin : ∀ n : ℕ, 1 ≤ n →
      {x ∈ Metric.sphere (0 : E) (1 / 2) | ((ψ (FreeGroup.of 0)) ^ n) x = x}.Finite := by
    intro n hn
    rw [(map_pow ψ (FreeGroup.of 0) n).symm]
    obtain ⟨hdet, hne⟩ := hprop ((FreeGroup.of 0) ^ n) (of_pow_ne_one n hn)
    exact fixed_set_half_sphere_finite _ hdet hne
  exact ⟨ψ (FreeGroup.of 0),
    exists_not_fixed_in_uncountable_sphere (ψ (FreeGroup.of 0)) half_sphere_uncountable hfin⟩

end Library.Geometry.BanachTarski.UncountableSphere
