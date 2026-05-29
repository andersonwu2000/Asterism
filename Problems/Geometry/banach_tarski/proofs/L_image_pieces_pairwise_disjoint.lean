-- Lift F₂'s 5-piece disjointness through the injective hom φ.
-- Two sub-goals: (1) `pairwise_disjoint_image_of_injective` — an abstract transfer: an
--   injective image preserves a pairwise-disjoint family, stated with the image-family `f`
--   and a pointwise bridge `∀ i, f i = ψ '' g i` so the goal's match-family is inferred
--   (`refine` unifies `f`) rather than rewritten; (2) `pieces_preimage_pairwise_disjoint`
--   — the base disjointness of the underlying FreeGroup pieces (empty-word vs head-letter).
-- Combine: feed the base as `g`, discharge the bridge by `cases o <;> rfl` (concrete
--   constructors make both matchers reduce definitionally).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11414

namespace Problems.Geometry.banach_tarski

def image_pieces_pairwise_disjoint := @Problems.Geometry.banach_tarski.s11414

end Problems.Geometry.banach_tarski
