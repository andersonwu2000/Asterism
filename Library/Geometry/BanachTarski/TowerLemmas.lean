import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.Order.BourbakiWitt
import Mathlib.Order.CompletePartialOrder
import Library.Geometry.BanachTarski.Defs

/-!
# Tower lemmas for the Banach–Tarski paradox

This file establishes combinatorial lemmas about the *orbit tower*
`⋃ n, (φ (FreeGroup.of 1))⁻¹ ^ n '' D` used in the proof of the Banach–Tarski paradox,
where `D` is the set of elements of `M` whose free-group address has empty reduced word.

## Main statements

- `length_toWord_inv_pow`: The reduced word of `(FreeGroup.of 1)⁻¹ ^ k` has length `k`.
- `wrd_eq_inv_pow_of_tower_image`: For `z` in the `k`-th tower orbit,
  `wrd z = (FreeGroup.of 1)⁻¹ ^ k`.
- `orbit_tower_disjoint`: The orbit-tower layers are pairwise disjoint.
- `eq_one_of_toWord_head_none`: A free-group element with empty reduced word equals `1`.
- `tower_first_letter_ne_zero`: The head letter of `(FreeGroup.of 1)⁻¹ ^ m` is never `0`.
- `tower_subset_source`: The orbit tower is contained in the source set.
-/

open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.TowerLemmas

/-- The reduced word of `(FreeGroup.of (1 : Fin 2))⁻¹ ^ k` has length `k`. -/
theorem length_toWord_inv_pow (k : ℕ) :
    (FreeGroup.toWord (((FreeGroup.of (1:Fin 2))⁻¹) ^ k)).length = k := by norm_num

/-- If `z` belongs to the `k`-th layer of the orbit tower, then
`wrd z = (FreeGroup.of (1 : Fin 2))⁻¹ ^ k`.

The orbit tower is built by iterating `φ (FreeGroup.of 1)⁻¹` on the set `D` of elements of
`M` with empty free-group address, and `wrd` is the address function satisfying
`wrd (φ w • x) = w * wrd x`. -/
theorem wrd_eq_inv_pow_of_tower_image
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x)
    (k : ℕ) (z : E)
    (hz : z ∈ ((φ (FreeGroup.of 1))⁻¹ ^ k) ''
        {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none}) :
    wrd z = ((FreeGroup.of (1:Fin 2))⁻¹) ^ k := by
  obtain ⟨x, ⟨hxM, hhead⟩, rfl⟩ := hz
  have hnil : FreeGroup.toWord (wrd x) = [] := by
    cases h : FreeGroup.toWord (wrd x) with
    | nil => rfl
    | cons a t => simp [h] at hhead
  have hwrd_x : wrd x = 1 := by
    apply FreeGroup.toWord_injective
    rw [hnil, FreeGroup.toWord_one]
  have hkey : ((φ (FreeGroup.of 1))⁻¹ ^ k) x =
      φ ((FreeGroup.of (1:Fin 2))⁻¹ ^ k) • x := by
    simp only [map_pow, map_inv]; rfl
  rw [hkey]
  have hcoh2 := (hcoh x hxM ((FreeGroup.of (1:Fin 2))⁻¹ ^ k)).2
  rw [hwrd_x, mul_one] at hcoh2
  exact hcoh2

/-- The layers of the orbit tower are pairwise disjoint.

For `D = {x ∈ M | (FreeGroup.toWord (wrd x)).head? = none}`, the sets
`(φ (FreeGroup.of 1))⁻¹ ^ i '' D` are pairwise disjoint. Disjointness follows because the
`wrd` address of any element in the `i`-th layer equals `(FreeGroup.of 1)⁻¹ ^ i`,
which has length `i` — a strictly monotone invariant. -/
theorem orbit_tower_disjoint
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (_hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    Pairwise (fun i j : ℕ => Disjoint
        (((φ (FreeGroup.of 1))⁻¹ ^ i) ''
          {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none})
        (((φ (FreeGroup.of 1))⁻¹ ^ j) ''
          {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none})) := by
  intro i j hij
  rw [Set.disjoint_left]
  rintro y hyi hyj
  apply hij
  have key : ((FreeGroup.of (1:Fin 2))⁻¹) ^ i = ((FreeGroup.of (1:Fin 2))⁻¹) ^ j :=
    (wrd_eq_inv_pow_of_tower_image φ M rep wrd hcoh i y hyi).symm.trans
      (wrd_eq_inv_pow_of_tower_image φ M rep wrd hcoh j y hyj)
  have hcong := congrArg (fun w => (FreeGroup.toWord w).length) key
  simpa [length_toWord_inv_pow] using hcong

/-- A free-group element of `FreeGroup (Fin 2)` whose reduced word has no head equals `1`. -/
theorem eq_one_of_toWord_head_none : ∀ (w : FreeGroup (Fin 2)),
    (FreeGroup.toWord w).head? = none → w = 1 := by norm_num

/-- The first letter of the reduced word of `(FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹ ^ m`
is never `0`. The reduced word equals `List.replicate m (1, false)`, so its head has first
component `1 ≠ 0`. -/
theorem tower_first_letter_ne_zero : ∀ m : ℕ,
    ¬ (FreeGroup.toWord ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹ ^ m)).head?.map Prod.fst
      = some 0 := by
  intro m
  have hgen : ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹) = FreeGroup.mk [(1, false)] := by
    rw [FreeGroup.of, FreeGroup.inv_mk]; rfl
  have hred : ∀ k : ℕ,
      FreeGroup.reduce (List.replicate k (1, false) : List (Fin 2 × Bool))
        = List.replicate k (1, false) := by
    intro k
    induction k with
    | zero => rfl
    | succ k ih =>
      rw [List.replicate_succ, FreeGroup.reduce.cons, ih]
      cases k with
      | zero => rfl
      | succ j => rw [List.replicate_succ]; simp
  have hpow : ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹) ^ m
      = FreeGroup.mk (List.replicate m (1, false)) := by
    induction m with
    | zero => rfl
    | succ k ih =>
      rw [pow_succ, ih, hgen, FreeGroup.mul_mk, ← List.replicate_succ']
  have hw : FreeGroup.toWord ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹ ^ m)
      = List.replicate m (1, false) := by
    rw [hpow, FreeGroup.toWord_mk, hred]
  rw [hw]
  cases m with
  | zero => simp
  | succ n => simp [List.replicate_succ]

/-- The orbit tower is contained in the source set.

Each element of `⋃ n, (φ (FreeGroup.of 1))⁻¹ ^ n '' D` lies in `M` and has a free-group
address whose first letter (if any) is not `0`. -/
theorem tower_subset_source
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    (⋃ n : ℕ, ((φ (FreeGroup.of 1))⁻¹ ^ n) ''
        {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none})
      ⊆ {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} := by
  intro x hx
  simp only [Set.mem_iUnion, Set.mem_image] at hx
  obtain ⟨n, y, ⟨hyM, hyhead⟩, rfl⟩ := hx
  have h_tower := tower_first_letter_ne_zero
  have h_empty := eq_one_of_toWord_head_none
  have hbridge : ((φ (FreeGroup.of 1))⁻¹ ^ n) y = φ ((FreeGroup.of 1)⁻¹ ^ n) • y := by
    rw [map_pow, map_inv]; rfl
  rw [Set.mem_setOf_eq, hbridge]
  refine ⟨hinv _ _ hyM, ?_⟩
  have hwrd : wrd (φ ((FreeGroup.of 1)⁻¹ ^ n) • y) = (FreeGroup.of 1)⁻¹ ^ n := by
    rw [(hcoh y hyM ((FreeGroup.of 1)⁻¹ ^ n)).2, h_empty (wrd y) hyhead, mul_one]
  rw [hwrd]
  exact h_tower n

end Library.Geometry.BanachTarski.TowerLemmas
