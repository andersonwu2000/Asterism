-- Build the orbit address from a general orbit section + freeness uniqueness.
-- `orbit_section_exists` gives a representative `rep` and word `wrd` with
-- `φ (wrd x) • rep x = x` and `rep` constant on each F₂-orbit (no freeness/M needed —
-- pure Quotient.out on the orbit relation). The cocycle word equation
-- `wrd (φ w • x) = w * wrd x` then follows from freeness uniqueness on M
-- (`free_action_word_unique`): both `φ (wrd (φ w•x)) • rep x` and `φ (w * wrd x) • rep x`
-- equal `φ w • x`, and `rep x ∈ M`, so the stabilizing words coincide. Each sub-goal is
-- strictly simpler: the section drops the cocycle equation and all M-hypotheses; the
-- uniqueness lemma is a single hfree application with no Equidecomp/orbit structure.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11474

namespace Problems.Geometry.banach_tarski

def orbit_address_of_free_action := @Problems.Geometry.banach_tarski.s11474

end Problems.Geometry.banach_tarski
