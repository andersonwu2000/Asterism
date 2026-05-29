-- Direct: (R θ)^n = R(n·θ) by hpow, and hno says R(n·θ) maps D outside D.
-- Disjoint via Set.disjoint_left: any x in the image equals R(n·θ) p with p∈D,
-- so x∈D contradicts hno.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11446

namespace Problems.Geometry.banach_tarski

def rotation_shift_disjoint_of_no_collision := @Problems.Geometry.banach_tarski.s11446

end Problems.Geometry.banach_tarski
