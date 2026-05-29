import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_pairwise_disjoint_image_of_injective
import Problems.Geometry.banach_tarski.proofs.L_pieces_preimage_pairwise_disjoint

namespace Problems.Geometry.banach_tarski

-- Lift F₂'s 5-piece disjointness through the injective hom φ.
-- Two sub-goals: (1) `pairwise_disjoint_image_of_injective` — an abstract transfer: an
--   injective image preserves a pairwise-disjoint family, stated with the image-family `f`
--   and a pointwise bridge `∀ i, f i = ψ '' g i` so the goal's match-family is inferred
--   (`refine` unifies `f`) rather than rewritten; (2) `pieces_preimage_pairwise_disjoint`
--   — the base disjointness of the underlying FreeGroup pieces (empty-word vs head-letter).
-- Combine: feed the base as `g`, discharge the bridge by `cases o <;> rfl` (concrete
--   constructors make both matchers reduce definitionally).
theorem s11414 {H : Type*} [Group H]
    (φ : FreeGroup (Fin 2) →* H) (hφ : Function.Injective φ) :
    (Set.univ : Set (Option (Fin 2 × Bool))).PairwiseDisjoint
      (fun o => match o with
        | none   => φ '' {w : FreeGroup (Fin 2) | FreeGroup.toWord w = []}
        | some p => φ '' {w : FreeGroup (Fin 2) | (FreeGroup.toWord w).head? = some p}) := by
  refine pairwise_disjoint_image_of_injective φ hφ Set.univ
    (fun o => match o with
      | none   => {w : FreeGroup (Fin 2) | FreeGroup.toWord w = []}
      | some p => {w : FreeGroup (Fin 2) | (FreeGroup.toWord w).head? = some p})
    _ ?_ pieces_preimage_pairwise_disjoint
  intro o; cases o <;> rfl

end Problems.Geometry.banach_tarski
