-- `formCoordChange I k i j` is definitionally `compContinuousLinearMapCLM ∘ coordChange j i`;
-- compose global continuity of `compContinuousLinearMapCLM` (in its CLM argument) with the
-- `continuousOn_coordChange` structure field, then flip the intersection with `inter_comm`.
import Mathlib
import Problems.Geometry.stokes_form_coord_cont.Defs
import Problems.Geometry.stokes_form_coord_cont.proofs._strategy_s11666

namespace Problems.Geometry.stokes_form_coord_cont

def main := @Problems.Geometry.stokes_form_coord_cont.s11666

end Problems.Geometry.stokes_form_coord_cont
