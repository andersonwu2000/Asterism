-- (A) of the Hausdorff→S²∖D split: build the F₂↪SO(3)↪(E≃ᵢE) embedding φ and take D as
-- its countable fixed-point set on the unit sphere; φ then acts on S²∖D invariantly and
-- fixed-point-freely, with 0∉D since D⊆S².
-- Sub-goal `exists_free_isometry_embedding` (geometry): an injective φ fixing the origin
--   whose every nontrivial word has a FINITE fixed set on S² (the rotation/det-1 bricks).
-- Sub-goal `fixed_free_action_off_countable` (abstract): from such a φ, take D = the
--   union of those fixed sets — countable (FreeGroup Fin 2 is countable + each fiber finite),
--   φ-invariant and fixed-point-free off D — no sphere/free-group geometry left.
-- Combinator: obtain φ from (A), feed it to (B), repackage with the shared φ.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11463

namespace Problems.Geometry.banach_tarski

def exists_free_isometry_action_off_countable := @Problems.Geometry.banach_tarski.s11463

end Problems.Geometry.banach_tarski
