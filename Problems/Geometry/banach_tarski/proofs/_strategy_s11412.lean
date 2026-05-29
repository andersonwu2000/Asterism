import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

open Pointwise

-- Direct proof: push the translate identity `a • W = univ \ V` through φ.
-- h2: injective image preserves set-difference (`Set.image_diff hφ`) and
--     `φ '' univ = φ.range` (`Set.image_univ` + `MonoidHom.coe_range`).
-- h1: image of a left-translate is the translate of the image, element-wise
--     via `map_mul` (no dedicated mathlib lemma `Set.image_smul_set` exists).
-- Then rewrite `φ '' (a • W) = φ '' (univ \ V)` by both to land on the goal.
theorem s11412
    {G H : Type*} [Group G] [Group H] (φ : G →* H)
    (hφ : Function.Injective φ) (a : G) (W V : Set G)
    (hWV : (a • W : Set G) = Set.univ \ V) :
    (φ a • (φ '' W) : Set H) = (φ.range : Set H) \ (φ '' V)  := by
  have h2 : (φ '' (Set.univ \ V) : Set H) = (φ.range : Set H) \ (φ '' V) := by
    rw [Set.image_diff hφ, Set.image_univ, MonoidHom.coe_range]
  have h1 : (φ '' (a • W) : Set H) = (φ a • (φ '' W) : Set H) := by
    ext y
    simp only [Set.mem_image, Set.mem_smul_set, smul_eq_mul]
    constructor
    · rintro ⟨x, ⟨w, hw, rfl⟩, rfl⟩
      exact ⟨φ w, ⟨w, hw, rfl⟩, by rw [map_mul]⟩
    · rintro ⟨z, ⟨w, hw, rfl⟩, rfl⟩
      exact ⟨a * w, ⟨w, hw, rfl⟩, by rw [map_mul]⟩
  have key : (φ '' (a • W) : Set H) = (φ '' (Set.univ \ V) : Set H) := by rw [hWV]
  rw [h1, h2] at key
  exact key

end Problems.Geometry.banach_tarski
