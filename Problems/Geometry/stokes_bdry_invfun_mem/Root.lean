-- Decomposition: (A) model-side computation — `faceEmbed z` lies in the frontier of the
-- half-space model's range (its 0-th coordinate vanishes); (B) chart transfer — any
-- on-target point of `frontier (range 𝓡∂(n+1))` is pulled back by the extended chart's
-- symm into the manifold boundary. Root = B at `x := p.val`, `y := faceEmbed z`, fed by A.
import Mathlib
import Problems.Geometry.stokes_bdry_invfun_mem.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.proofs._strategy_s11667

namespace Problems.Geometry.stokes_bdry_invfun_mem

def main := @Problems.Geometry.stokes_bdry_invfun_mem.s11667

end Problems.Geometry.stokes_bdry_invfun_mem
