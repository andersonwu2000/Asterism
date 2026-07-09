import Library.Geometry.BanachTarski.Defs
import Library.Geometry.BanachTarski.DisjointOrbit
import Library.Geometry.BanachTarski.UncountableSphere

/-!
# Conjugate orbits for the Banach–Tarski construction

This file builds the key isometry used to absorb the origin `{0}` into the
Banach–Tarski decomposition. Given a linear isometry `R : E ≃ₗᵢ[ℝ] E` and a
centre `c : E`, the **conjugated isometry** `ρ x = R (x - c) + c` shifts the
rotation axis from the origin to `c`. The origin-orbit of `ρ` satisfies the
closed form `(ρ ^ n) 0 = c - (R ^ n) c`, which stays in the unit closed ball
when `‖c‖ ≤ 1 / 2` and never returns to `0` for `n ≥ 1` when `R` has an
irrational rotation angle at `c`.

## Main statements

* `conjugate_orbit_formula` — closed form `(ρ ^ n) 0 = c - (R ^ n) c` by induction.
* `conjugate_orbit_ne_zero` — the orbit point is nonzero whenever `n ≥ 1` and `R`
  has no periodic point at `c`.
* `conjugate_orbit_norm_bound` — the orbit stays in `Metric.closedBall 0 1`
  when `‖c‖ ≤ 1 / 2`.
* `exists_conjugated_isometry` — existence of `ρ` as an `E ≃ᵢ E`.
* `conjugate_origin_orbit` — combines the above to produce `ρ` with a bounded
  injective origin-orbit.
* `exists_bounded_injective_origin_orbit` — unconditional version obtained from
  `exists_small_irrational_rotation`.
* `bounded_injective_rotation_orbit` — lifts the pointwise properties to the
  set-level disjointness statement needed for the paradox.
-/

open Library.Geometry.BanachTarski.Defs
open Library.Geometry.BanachTarski.DisjointOrbit
open Library.Geometry.BanachTarski.UncountableSphere

namespace Library.Geometry.BanachTarski.ConjugateOrbit

set_option maxHeartbeats 0 in
-- `(ρ ^ n : E ≃ᵢ E)` elaboration on `EuclideanSpace ℝ (Fin 3)` exceeds the default limit
/-- Closed form for the origin-orbit of the conjugated rotation `ρ x = R (x - c) + c`.
By induction on `n`: the base case `n = 0` is immediate from `simp`, and the inductive
step rewrites `ρ ^ (k + 1) = ρ ∘ ρ ^ k`, applies the inductive hypothesis and the
defining equation `hρ`, uses linearity of `R` and `R ^ (k + 1) = R ∘ R ^ k`,
then closes by abelian-group algebra. -/
theorem conjugate_orbit_formula (ρ : E ≃ᵢ E) (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hρ : ∀ x : E, ρ x = R (x - c) + c) :
    ∀ n : ℕ, (ρ ^ n) 0 = c - (R ^ n) c := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    rw [pow_succ', IsometryEquiv.coe_mul, Function.comp_apply, ih, hρ,
      pow_succ', LinearIsometryEquiv.coe_mul, Function.comp_apply]
    simp
    abel


/-- For a linear isometry `R : E ≃ₗᵢ[ℝ] E` and centre `c : E`, if no positive power
of `R` fixes `c` (hypothesis `hfix : ∀ n ≥ 1, (R ^ n) c ≠ c`), then
`c - (R ^ n) c ≠ 0` for all `n ≥ 1`. -/
theorem conjugate_orbit_ne_zero (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hfix : ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c) (n : ℕ) (hn : 1 ≤ n) :
    c - (R ^ n) c ≠ 0 :=
  sub_ne_zero_of_ne fun a ↦ hfix n hn (id (Eq.symm a))

/-- For a linear isometry `R : E ≃ₗᵢ[ℝ] E` and centre `c : E` with `‖c‖ ≤ 1 / 2`,
the orbit point `c - (R ^ n) c` has norm at most `1` for every `n : ℕ`. -/
theorem conjugate_orbit_norm_bound (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hc : ‖c‖ ≤ 1 / 2) (n : ℕ) :
    ‖c - (R ^ n) c‖ ≤ 1 := by
  calc ‖c - (R ^ n) c‖
      ≤ ‖c‖ + ‖(R ^ n) c‖ := norm_sub_le _ _
    _ = ‖c‖ + ‖c‖ := by rw [(R ^ n).norm_map]
    _ ≤ 1 := by linarith

/-- Given a linear isometry `R : E ≃ₗᵢ[ℝ] E` and a centre `c : E`, there exists an
isometry `ρ : E ≃ᵢ E` satisfying `ρ x = R (x - c) + c` for all `x`. -/
theorem exists_conjugated_isometry (R : E ≃ₗᵢ[ℝ] E) (c : E) :
    ∃ ρ : E ≃ᵢ E, ∀ x : E, ρ x = R (x - c) + c := by
  refine ⟨⟨⟨fun x => R (x - c) + c, fun y => R.symm (y - c) + c, ?_, ?_⟩, ?_⟩, fun x => rfl⟩
  · intro x; simp
  · intro y; simp
  · intro x y
    change edist (R (x - c) + c) (R (y - c) + c) = edist x y
    rw [edist_add_right, R.isometry (x - c) (y - c), edist_sub_right]

/-- Conjugating the linear isometry `R` by the translation `x ↦ x - c` yields an
isometry `ρ x = R (x - c) + c` whose origin-orbit satisfies the closed form
`(ρ ^ n) 0 = c - R ^ n c`. When `‖c‖ ≤ 1 / 2` the orbit stays in the unit closed
ball, and when no positive power of `R` fixes `c` the orbit never returns to `0`. -/
theorem conjugate_origin_orbit (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hc : ‖c‖ ≤ 1 / 2) (hfix : ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c) :
    ∃ ρ : E ≃ᵢ E,
      (∀ n : ℕ, (ρ ^ n) 0 ∈ Metric.closedBall (0 : E) 1) ∧
      (∀ n : ℕ, 1 ≤ n → (ρ ^ n) 0 ≠ 0) := by
  obtain ⟨ρ, hρ⟩ := exists_conjugated_isometry R c
  have horbit := conjugate_orbit_formula ρ R c hρ
  refine ⟨ρ, ?_, ?_⟩
  · intro n
    rw [Metric.mem_closedBall, dist_zero_right, horbit n]
    exact conjugate_orbit_norm_bound R c hc n
  · intro n hn
    rw [horbit n]
    exact conjugate_orbit_ne_zero R c hfix n hn

/-- There exists an isometry `ρ : E ≃ᵢ E` such that every point of the origin-orbit
`{(ρ ^ n) 0 | n : ℕ}` lies in the unit closed ball and the orbit is injective
(`(ρ ^ n) 0 ≠ 0` for all `n ≥ 1`).

The isometry is obtained by applying `conjugate_origin_orbit` to the linear rotation
`R` and small vector `c` supplied by `exists_small_irrational_rotation`. -/
theorem exists_bounded_injective_origin_orbit :
    ∃ ρ : E ≃ᵢ E,
      (∀ n : ℕ, (ρ ^ n) 0 ∈ Metric.closedBall (0 : E) 1) ∧
      (∀ n : ℕ, 1 ≤ n → (ρ ^ n) 0 ≠ 0) := by
  obtain ⟨R, c, hc, hfix⟩ := exists_small_irrational_rotation
  exact conjugate_origin_orbit R c hc hfix

/-- There exists an isometry `ρ : E ≃ᵢ E` such that the union of singleton orbits
`⋃ n, (ρ ^ n) '' {0}` is contained in the unit closed ball and the singleton images
are pairwise disjoint.

The containment follows from `exists_bounded_injective_origin_orbit` via
`Set.iUnion_subset` and `Set.image_singleton`; the pairwise disjointness follows from
`pairwise_disjoint_of_shift_disjoint` applied to the pointwise injectivity condition. -/
theorem bounded_injective_rotation_orbit :
    ∃ ρ : E ≃ᵢ E,
      (⋃ n : ℕ, (ρ ^ n) '' ({0} : Set E)) ⊆ Metric.closedBall (0 : E) 1 ∧
      Pairwise (fun i j : ℕ =>
        Disjoint ((ρ ^ i) '' ({0} : Set E)) ((ρ ^ j) '' ({0} : Set E))) := by
  obtain ⟨ρ, hball, hne⟩ := exists_bounded_injective_origin_orbit
  refine ⟨ρ, ?_, ?_⟩
  · apply Set.iUnion_subset
    intro n
    rw [Set.image_singleton]
    intro x hx
    rw [Set.mem_singleton_iff] at hx
    subst hx
    exact hball n
  · apply pairwise_disjoint_of_shift_disjoint ρ ({0} : Set E)
    intro n hn
    rw [Set.image_singleton]
    rw [Set.disjoint_singleton]
    exact hne n hn

end Library.Geometry.BanachTarski.ConjugateOrbit
