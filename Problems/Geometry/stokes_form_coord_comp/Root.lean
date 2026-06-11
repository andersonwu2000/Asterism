-- Direct proof (leaf bypass): extensionality + simp-unfold of `formCoordChange`
-- reduces both sides to pointwise applications of `v`; `congr`/`funext` exposes the
-- tangent transition cocycle, closed by `(tangentBundleCore I M).coordChange_comp`
-- with indices `(l, j, i)` (contravariant index swap in `formCoordChange`).
import Mathlib
import Problems.Geometry.stokes_form_coord_comp.Defs
import Problems.Geometry.stokes_form_coord_comp.proofs._strategy_s11665

namespace Problems.Geometry.stokes_form_coord_comp

def main := @Problems.Geometry.stokes_form_coord_comp.s11665

end Problems.Geometry.stokes_form_coord_comp
