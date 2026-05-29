-- T preserves W (W.map T ≤ W) and T is a linear equiv, so finrank is preserved;
-- in finite dimension a submodule contained in W with equal finrank IS W, hence
-- W.map T = W, so every w ∈ W has a preimage y ∈ W. Direct (no sub-goals).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11424

namespace Problems.Geometry.banach_tarski

def invariant_submodule_image_surj := @Problems.Geometry.banach_tarski.s11424

end Problems.Geometry.banach_tarski
