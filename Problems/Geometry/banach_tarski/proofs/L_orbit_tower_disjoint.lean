-- Orbit tower D, ρ^i''D (ρ = φ(of 1)⁻¹), is pairwise disjoint because the
-- address `wrd` of any element of ρ^i''D equals (of 1)⁻¹^i (hcoh: wrd(φ w•x)=w*wrd x,
-- with wrd x=1 on D since head?=none), and the reduced word (of 1)⁻¹^i has length i —
-- a strictly-increasing invariant, so i≠j ⇒ disjoint.
-- Sub-goals: `wrd_of_tower_image` (address of a tower element) and
-- `length_pow_inv_of` (length of the pure FreeGroup power). Combiner: a shared y
-- forces (of 1)⁻¹^i = (of 1)⁻¹^j, take toWord-length to get i = j ⊥ hij.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11490

namespace Problems.Geometry.banach_tarski

def orbit_tower_disjoint := @Problems.Geometry.banach_tarski.s11490

end Problems.Geometry.banach_tarski
