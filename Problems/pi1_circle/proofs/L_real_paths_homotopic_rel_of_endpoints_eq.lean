-- Affine (straight-line) homotopy `H(t,x) = lineMap (f x) (g x) t` in ℝ:
-- `ContinuousMap.Homotopy.affine f g` already supplies the underlying `Homotopy`;
-- the relative property at `x ∈ {0,1}` collapses via `Path.segment_same` once
-- `h0`/`h1` rewrite the two endpoints to equal points.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10703

namespace Problems.pi1_circle

def real_paths_homotopic_rel_of_endpoints_eq := @Problems.pi1_circle.s10703

end Problems.pi1_circle
