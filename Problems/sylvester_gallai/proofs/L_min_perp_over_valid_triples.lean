-- Generalise the perpendicular-distance function to an abstract `f`; the
-- existence of an arg-minimum over valid triples is independent of the
-- specific function form. Sub-goal `min_arg_valid_triple` does the
-- Finset.exists_min_image extraction; combinator instantiates `f` with
-- the perpendicular-distance squared.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s10208

namespace Problems.sylvester_gallai

def min_perp_over_valid_triples := @Problems.sylvester_gallai.s10208

end Problems.sylvester_gallai
