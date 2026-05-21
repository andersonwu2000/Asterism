-- Per-cell Cauchy quadrilateral identity: the four corners
-- BL = H(i/N,j/N), BR = H((i+1)/N,j/N), TR = H((i+1)/N,(j+1)/N), TL = H(i/N,(j+1)/N)
-- live in `Metric.ball (c i j) (r i j) ⊆ U` (via `hgrid`); since g is analytic on U
-- and hence DifferentiableOn ℂ on the ball, the closed quadrilateral integral
-- vanishes by `cell_quad_identity_on_ball`, yielding directly the desired
-- (vert-left − vert-right) = (bot − top) identity.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10644

namespace Problems.residue_thm

def cell_quad_chord_vert_diff := @Problems.residue_thm.s10644

end Problems.residue_thm
