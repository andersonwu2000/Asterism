-- Reduce subtype homeomorphism to existence of a self-homeomorphism of the
-- ambient Euclidean space sending T onto the closed unit ball. The standard
-- realization is the Minkowski gauge rescale, but this strategy abstracts
-- that geometric content into a single sub-goal; the parent only does
-- subtype/image plumbing via `Homeomorph.image` + `Homeomorph.setCongr`.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10812

namespace Problems.Topology.brouwer_fixed_point

def compact_convex_origin_interior_homeo_unit_ball := @Problems.Topology.brouwer_fixed_point.s10812

end Problems.Topology.brouwer_fixed_point
