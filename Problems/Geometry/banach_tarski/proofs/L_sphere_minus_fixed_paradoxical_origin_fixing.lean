-- Origin-fixing strengthening of the Hausdorff→S²∖D paradox (mirror of s11459).
-- Geometric half is cited inline from PROVED bricks: exists_free_isometry_embedding (s11470)
-- gives an injective φ : F₂ ↪ (E≃ᵢE) with the EXTRA datum `∀ w, φ w 0 = 0` (every word is an
-- origin-fixing rotation) plus per-word finite fixed sets; fixed_free_action_off_countable
-- (s11471) takes its countable fixed-point union D ⊆ S² (0∉D), invariant + fixed-point-free off D.
-- The single sub-goal `paradoxical_of_free_isometry_action_origin_fixing` is the abstract lift:
-- it reuses the F₂ two-piece split (cf. s11464) but ADDITIONALLY exposes the realizing Finsets
-- Sf,Sg (shape {1, φ(of i)} / Hilbert-hotel tower of φ(of 1)-powers), all origin-fixing via hfix0.
-- Combinator: obtain D,φ + props inline, feed M := S²∖D and hfix0 to the lift.
-- Strictly simpler: the sub-goal drops ALL sphere/fixed-point geometry (abstract M).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11508

namespace Problems.Geometry.banach_tarski

def sphere_minus_fixed_paradoxical_origin_fixing := @Problems.Geometry.banach_tarski.s11508

end Problems.Geometry.banach_tarski
