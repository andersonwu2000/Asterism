-- Skolemise the per-pole data: prove `∀ a ∈ T, ∃ (r, Pₐ, hₐ)` carrying the
-- isolating-radius + principal-part decomposition pointwise, then promote via
-- `Classical.choose` (the `choose` tactic) to global functions `P, R, h` and
-- exhibit the parent existential. The single sub-goal is strictly simpler — it
-- drops the global-function coherence requirement, leaving only the local
-- combination of (a) an isolating ball around each pole inside `U` separated
-- from the other elements of `T`, and (b) one application of the already-proved
-- `principal_part_extraction_at_singularity` toolkit lemma to the punctured ball.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10458

namespace Problems.residue_thm

def per_pole_principal_part_data := @Problems.residue_thm.s10458

end Problems.residue_thm
