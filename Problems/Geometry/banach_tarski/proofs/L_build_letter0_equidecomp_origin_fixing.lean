-- Origin-fixing refinement of build_letter0_equidecomp (s11472): same piecewise map
-- (f = id on A, g0•· on B, g0 = φ(of 0)) reconstructed inline from the proved bricks,
-- now ALSO exposing the realizing Finset Sf = {1, g0} and proving every element fixes 0.
-- The IsDecompOn witness is the explicit {1, g0} (id-or-shift case split); origin-fixing
-- is (1) 0 = 0 and g0 0 = φ(of 0) 0 = 0 via hfix0. No new sub-goals — leaf reconstruction.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11523

namespace Problems.Geometry.banach_tarski

def build_letter0_equidecomp_origin_fixing := @Problems.Geometry.banach_tarski.s11523

end Problems.Geometry.banach_tarski
