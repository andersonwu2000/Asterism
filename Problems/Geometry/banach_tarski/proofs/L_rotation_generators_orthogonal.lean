-- Split the orthogonality conjunction into the two independent matrix computations.
-- h_a / h_b each verify Mᵀ * M = 1 for one concrete generator (pure √2 arithmetic),
-- strictly simpler than the parent since only one matrix is in scope per sub-goal.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11389

namespace Problems.Geometry.banach_tarski

def rotation_generators_orthogonal := @Problems.Geometry.banach_tarski.s11389

end Problems.Geometry.banach_tarski
