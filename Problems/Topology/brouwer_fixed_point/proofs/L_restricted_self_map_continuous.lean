import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Builder
-- restricted_self_map_continuous: ContinuousOn.restrict + subtype_mk close the goal
-- `hcont.restrict` gives `Continuous (fun s : S => f s.val)`; `subtype_mk` lifts to `S → S`.
theorem restricted_self_map_continuous
    {α : Type*} [TopologicalSpace α] {S : Set α}
    {f : α → α} (hcont : ContinuousOn f S) (hmaps : Set.MapsTo f S S) :
    Continuous (fun s : S => (⟨f s.val, hmaps s.property⟩ : S)) :=
  hcont.restrict.subtype_mk (fun s => hmaps s.property)

end Problems.Topology.brouwer_fixed_point
