import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_freegroup_cover

namespace Problems.Geometry.banach_tarski

-- φ-images of the 5 FreeGroup pieces cover φ.range.
-- key: φ '' distributes over the indexed union (cases on Option, defeq per branch).
-- h_cover: `Set.iUnion_option` splits the Option-union into the empty-word piece ∪
--   the head-letter pieces; the match-free `freegroup_cover` (lone sub-goal) gives = univ.
-- Then φ '' univ = Set.range φ = ↑φ.range. The sub-goal is stated WITHOUT a `match`
--   (explicit ∪ / ⋃ p) so it carries no anonymous match-aux constant — avoids the
--   cross-file `match` defeq mismatch that an Option-match restatement would trigger.
theorem s11415 {H : Type*} [Group H]
    (φ : FreeGroup (Fin 2) →* H) (hφ : Function.Injective φ) :
    (⋃ o : Option (Fin 2 × Bool), match o with
        | none   => φ '' {w : FreeGroup (Fin 2) | FreeGroup.toWord w = []}
        | some p => φ '' {w : FreeGroup (Fin 2) | (FreeGroup.toWord w).head? = some p})
      = (φ.range : Set H)  := by
  have key : (⋃ o : Option (Fin 2 × Bool), match o with
        | none   => φ '' {w : FreeGroup (Fin 2) | FreeGroup.toWord w = []}
        | some p => φ '' {w : FreeGroup (Fin 2) | (FreeGroup.toWord w).head? = some p})
      = φ '' (⋃ o : Option (Fin 2 × Bool), match o with
        | none   => {w : FreeGroup (Fin 2) | FreeGroup.toWord w = []}
        | some p => {w : FreeGroup (Fin 2) | (FreeGroup.toWord w).head? = some p}) := by
    rw [Set.image_iUnion]
    congr 1
    ext o
    cases o <;> rfl
  rw [key]
  have h_cover : (⋃ o : Option (Fin 2 × Bool), match o with
        | none   => {w : FreeGroup (Fin 2) | FreeGroup.toWord w = []}
        | some p => {w : FreeGroup (Fin 2) | (FreeGroup.toWord w).head? = some p})
      = (Set.univ : Set (FreeGroup (Fin 2))) := by
    rw [Set.iUnion_option]
    exact freegroup_cover
  rw [h_cover, Set.image_univ, MonoidHom.coe_range]

end Problems.Geometry.banach_tarski
