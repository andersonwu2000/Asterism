-- Direct coordinate proof: `ext j`, split `j` via `Fin.cases` into the normal
-- coordinate `0` (where `h0` and `Fin.succ_ne_zero` kill every summand) and a
-- face coordinate `i.succ` (where `Pi.single_apply` + `Fin.succ_inj` collapse
-- the `faceEmbed` sum to the single matching term `w i.succ`).
import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs._strategy_s11670

namespace Problems.Geometry.stokes_bdry_chart

def face_embed_face_proj_of_coord_zero := @Problems.Geometry.stokes_bdry_chart.s11670

end Problems.Geometry.stokes_bdry_chart
