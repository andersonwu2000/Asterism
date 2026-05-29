-- Take D := the union, over nontrivial words w, of the fixed points of φ w on the unit sphere:
--   D = ⋃ (w ≠ 1) {x ∈ sphere 0 1 | φ w x = x}. Combinator: `refine ⟨D, …⟩` with five branches.
-- Sub-goal `sphere_fixed_union_countable` (Builder) — D is countable: the index FreeGroup (Fin 2)
--   is countable and each fiber is finite (hfin), so the union is countable; this drops all
--   action/geometry reasoning, hence strictly simpler.
-- Sub-goal `sphere_fixed_action_invariant` (Backward) — φ w • x ∈ sphere \ D for x ∈ sphere \ D:
--   φ w fixes 0 ⇒ it preserves the sphere, and the conjugation argument (w⁻¹vw fixes x whenever
--   v fixes φ w x) keeps φ w • x out of D; isolates a single conjunct of the parent.
-- The remaining three branches are immediate from the definition and closed inline:
--   D ⊆ sphere (each member set is a sphere subset); 0 ∉ D (0 ∉ sphere 0 1); freeness off D
--   (a fixed point on the sphere would itself lie in D, contradicting x ∉ D).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11471

namespace Problems.Geometry.banach_tarski

def fixed_free_action_off_countable := @Problems.Geometry.banach_tarski.s11471

end Problems.Geometry.banach_tarski
