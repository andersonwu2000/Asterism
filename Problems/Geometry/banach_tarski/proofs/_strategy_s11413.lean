import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_range_translate_eq_range_sdiff_of_injective
import Problems.Geometry.banach_tarski.proofs.L_translate_starts_eq_compl
import Problems.Geometry.banach_tarski.proofs.L_image_pieces_cover_range
import Problems.Geometry.banach_tarski.proofs.L_image_pieces_pairwise_disjoint

namespace Problems.Geometry.banach_tarski

open scoped Pointwise

-- Lift F₂'s 5-piece paradoxical split through the injective hom φ.
-- Conjuncts 3,4 (`tr i`) are proved INLINE here — each generator-translate is a
--   direct instance of the proved `range_translate_eq_range_sdiff_of_injective`
--   (s11412) fed by `translate_starts_eq_compl i` (rewritten compl→univ∖); this
--   keeps the FreeGroup-flavoured translate identity out of a Builder.
-- h_disj/h_cover: the φ-images of the empty-word piece + 4 head-letter pieces stay
--   pairwise-disjoint / cover φ.range (injectivity transports both) — the only two
--   structurally-bigger sub-goals.
theorem s11413
    {H : Type*} [Group H] (φ : FreeGroup (Fin 2) →* H)
    (hφ : Function.Injective φ) :
    let piece : Option (Fin 2 × Bool) → Set H :=
      fun o => match o with
        | none   => φ '' {w | FreeGroup.toWord w = []}
        | some p => φ '' {w | (FreeGroup.toWord w).head? = some p}
    (Set.univ : Set (Option (Fin 2 × Bool))).PairwiseDisjoint piece ∧
    (⋃ o, piece o) = (φ.range : Set H) ∧
    (φ (FreeGroup.of 0) • (φ '' {w | (FreeGroup.toWord w).head? = some (0, false)})
        = (φ.range : Set H) \ φ '' {w | (FreeGroup.toWord w).head? = some (0, true)}) ∧
    (φ (FreeGroup.of 1) • (φ '' {w | (FreeGroup.toWord w).head? = some (1, false)})
        = (φ.range : Set H) \ φ '' {w | (FreeGroup.toWord w).head? = some (1, true)}) := by
  intro piece
  have tr : ∀ i : Fin 2,
      φ (FreeGroup.of i) • (φ '' {w | (FreeGroup.toWord w).head? = some (i, false)})
        = (φ.range : Set H) \ φ '' {w | (FreeGroup.toWord w).head? = some (i, true)} := by
    intro i
    exact range_translate_eq_range_sdiff_of_injective φ hφ (FreeGroup.of i)
      {w | (FreeGroup.toWord w).head? = some (i, false)}
      {w | (FreeGroup.toWord w).head? = some (i, true)}
      (by rw [translate_starts_eq_compl, Set.compl_eq_univ_diff])
  refine ⟨?_, ?_, tr 0, tr 1⟩
  · exact image_pieces_pairwise_disjoint φ hφ
  · exact image_pieces_cover_range φ hφ

end Problems.Geometry.banach_tarski
