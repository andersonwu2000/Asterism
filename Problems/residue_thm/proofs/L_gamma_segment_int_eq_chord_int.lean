-- Use the row-0 ball-cover primitive at column j: g analytic on `Metric.ball (c 0 j) (r 0 j) ⊆ U`
-- gives a holomorphic primitive `F` on the ball. The γ-segment integral on `[j/N, (j+1)/N]`
-- equals `F (γ((j+1)/N)) - F (γ(j/N))` by FTC along the C¹ subpath (γ maps the subinterval into
-- the ball via `hH0` + `hgrid 0 j` at `τ=0`). The chord integral equals the same primitive
-- difference because the ball is convex (the lerp segment lies inside the ball). Both integrals
-- therefore coincide.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10631

namespace Problems.residue_thm

def gamma_segment_int_eq_chord_int := @Problems.residue_thm.s10631

end Problems.residue_thm
