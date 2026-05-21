-- Concordance via piecewise FTC on each ball of the cover.
-- (1) `piecewise_path_int_eq_on_ball` (per index i < n): the integrals of
--     `g(γ) γ'` and `g(η) η'` over [t i, t (i+1)] agree, because both curves
--     lie in the ball B_i ⊆ U on which `g` admits a primitive and they share
--     endpoint values η (t i) = γ (t i).
-- (2) `path_int_telescope_partition`: summing the per-piece equalities via
--     `intervalIntegral.sum_integral_adjacent_intervals` rebuilds the full
--     integrals over [0,1] and yields the concordance equality.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10492

namespace Problems.residue_thm

def path_int_eq_from_ball_cover_concordance := @Problems.residue_thm.s10492

end Problems.residue_thm
