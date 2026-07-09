-- Kelly's minimal-perpendicular-distance decomposition of Sylvester–Gallai.
-- by_contra ⇒ hAll (every pair of P has a 3rd collinear point); the flag finset
-- F = non-collinear triples (p,q,r) in P³ is nonempty (`flag_set_nonempty`);
-- minimise the algebraic perpendicular distance pd over F (`Finset.exists_min_image`);
-- the minimal flag contradicts hAll (`kelly_min_flag_false`), closing `False`.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s17697

namespace Problems.sylvester_gallai

def main := @Problems.sylvester_gallai.s17697

end Problems.sylvester_gallai
