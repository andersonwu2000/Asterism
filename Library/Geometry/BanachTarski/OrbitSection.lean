import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Library.Geometry.BanachTarski.Defs

/-!
# Orbit sections for group actions

This file constructs *orbit sections* — functions picking canonical representatives from
each orbit of a group action, together with a "word" mapping each element back to its
representative.

## Main statements

- `orbit_section_general`: for any group `G` acting on a type `α`, there exist a
  representative function `rep : α → α` and a word function `wrd : α → G` such that
  `wrd x • rep x = x` and `rep` is constant on each orbit.
- `orbit_section_exists`: specializes `orbit_section_general` to the action of
  `FreeGroup (Fin 2)` on `E` via an isometry homomorphism `φ`.
- `free_action_word_unique`: in a free action, the group element sending a representative
  to a point is unique.
- `orbit_address_of_free_action`: combines the above to give a canonical address
  `(rep x, wrd x)` for each orbit element, with compatible word arithmetic.
-/

open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.OrbitSection

/-- For any group `G` acting on a type `α`, there exist a representative function
`rep : α → α` constant on orbits and a word function `wrd : α → G` such that
`wrd x • rep x = x` for all `x`. This is a pure application of the axiom of choice via
`Quotient.out` on the orbit relation `MulAction.orbitRel`. -/
theorem orbit_section_general {G : Type*} [Group G] {α : Type*} [MulAction G α] :
    ∃ (rep : α → α) (wrd : α → G),
      (∀ x, wrd x • rep x = x) ∧
      (∀ x (w : G), rep (w • x) = rep x) := by
  classical
  let setoid := MulAction.orbitRel G α
  let rep : α → α := fun x => (Quotient.mk' (s := setoid) x).out
  have hmem : ∀ x : α, ∃ g : G, g • rep x = x := by
    intro x
    have heq : (Quotient.mk' (s := setoid) (rep x)) = Quotient.mk' x := Quotient.out_eq _
    rw [Quotient.eq'] at heq
    obtain ⟨g, hg⟩ := heq
    exact ⟨g⁻¹, by rw [← hg, inv_smul_smul]⟩
  have hrep : ∀ (x : α) (w : G), rep (w • x) = rep x := by
    intro x w
    simp only [rep]
    congr 1
    apply Quotient.sound
    simp only [MulAction.orbitRel_apply]
    exact MulAction.mem_orbit x w
  refine ⟨rep, fun x => (hmem x).choose, ?_, hrep⟩
  exact fun x => (hmem x).choose_spec

/-- An orbit section exists for the action of `FreeGroup (Fin 2)` on `E` via `φ`.
Specializes `orbit_section_general` via `MulAction.compHom`: equipping `E` with the action
`w • x := φ w • x` makes the abstract statement apply directly, since `compHom`'s scalar
multiplication is definitionally equal to `φ _ •`. -/
theorem orbit_section_exists (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) :
    ∃ (rep : E → E) (wrd : E → FreeGroup (Fin 2)),
      (∀ x, φ (wrd x) • rep x = x) ∧
      (∀ x (w : FreeGroup (Fin 2)), rep (φ w • x) = rep x) := by
  letI : MulAction (FreeGroup (Fin 2)) E := MulAction.compHom E φ
  exact orbit_section_general (G := FreeGroup (Fin 2)) (α := E)

/-- In a free action of `FreeGroup (Fin 2)` on a set `M`, the group element sending a
representative to a given point is unique: if `φ a • y = φ b • y` for `y ∈ M`,
then `a = b`. -/
theorem free_action_word_unique
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (y : E) (hy : y ∈ M) (a b : FreeGroup (Fin 2)) (h : φ a • y = φ b • y) :
    a = b := by
  -- φ a • y = φ b • y implies φ(a⁻¹*b) • y = y, hence a⁻¹*b = 1 by freeness, so b = a
  have key : a⁻¹ * b = 1 := by
    by_contra hne
    exact hfree (a⁻¹ * b) hne y hy (by
      rw [map_mul, mul_smul, map_inv, ← h, inv_smul_smul])
  exact inv_mul_eq_one.mp key

/-- Given a free action of `FreeGroup (Fin 2)` on an invariant set `M ⊆ E`, there exist a
representative function `rep : E → E` and a word function `wrd : E → FreeGroup (Fin 2)`
such that every `x ∈ M` satisfies `x = φ (wrd x) • rep x`, and the word arithmetic is
compatible: `wrd (φ w • x) = w * wrd x` for all `w`. -/
theorem orbit_address_of_free_action
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x) :
    ∃ (rep : E → E) (wrd : E → FreeGroup (Fin 2)),
      (∀ x ∈ M, x = φ (wrd x) • rep x) ∧
      (∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) := by
  obtain ⟨rep, wrd, haddr, hrep⟩ := orbit_section_exists φ
  have word_unique := free_action_word_unique φ M hfree
  refine ⟨rep, wrd, fun x _ => (haddr x).symm, fun x hx w => ⟨hrep x w, ?_⟩⟩
  have hr : (φ (wrd x))⁻¹ • x = rep x := by
    rw [inv_smul_eq_iff]; exact (haddr x).symm
  have hrepM : rep x ∈ M := by
    rw [← hr, ← map_inv]
    exact hinv _ _ hx
  have e1 : φ (wrd (φ w • x)) • rep x = φ w • x := by
    rw [← hrep x w]; exact haddr (φ w • x)
  have e2 : φ (w * wrd x) • rep x = φ w • x := by
    rw [map_mul, mul_smul, haddr x]
  exact word_unique (rep x) hrepM _ _ (e1.trans e2.symm)

end Library.Geometry.BanachTarski.OrbitSection
