-- Strengthen the proved sphere paradox (s11455) with origin-fixing witnessing data,
-- mirroring its two-layer structure but threading the IsDecompOn sets Sf/Sg whose
-- isometries all fix 0 (the F₂↪SO(3) generators and the absorption rotation are rotations).
-- (1) sphere_minus_fixed_paradoxical_origin_fixing: the free-action paradox of S²∖D with
--     origin-fixing decomposition sets — drops the absorption layer.
-- (2) absorb_countable_paradoxical_origin_fixing: transfer the S²∖D paradox to S² preserving
--     the origin-fixing data — generic Hilbert-hotel absorption, no free-group machinery.
-- Combinator: obtain D + the strengthened paradox from (1), feed to (2).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11503

namespace Problems.Geometry.banach_tarski

def sphere_paradoxical_origin_fixing := @Problems.Geometry.banach_tarski.s11503

end Problems.Geometry.banach_tarski
