-- Split the γ-path integral across N adjacent subintervals [j/N, (j+1)/N], then
-- equate each γ-segment integral with the chord integral via the row-0 ball-cover
-- primitive (γ-segment and chord both lie in ball (c 0 j) (r 0 j) ⊆ U, where g is
-- analytic and hence has a primitive on the ball).
-- (1) path_integral_split_subintervals — Builder: ∫₀¹ f = Σⱼ ∫_{j/N}^{(j+1)/N} f
--     via Finset.sum_integral_adjacent_intervals; integrand continuous on Icc 0 1.
-- (2) gamma_segment_int_eq_chord_int — Backward: per j, both segment and chord
--     integrals equal F(γ((j+1)/N)) - F(γ(j/N)) for the row-0 ball primitive F
--     (cite analytic_segment_primitive_diff via L_ auto-import; ball-convexity
--     places the chord inside ball (c 0 j) (r 0 j)).
-- Combinator: rewrite via hsplit, then Finset.sum_congr rfl hseg.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10617

namespace Problems.residue_thm

def gamma_int_eq_chord_polygon := @Problems.residue_thm.s10617

end Problems.residue_thm
