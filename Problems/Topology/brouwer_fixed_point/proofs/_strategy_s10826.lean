import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_brouwer_homeo_dispatch
import Problems.Topology.brouwer_fixed_point.proofs.L_brouwer_transport_via_homeo

namespace Problems.Topology.brouwer_fixed_point

-- Dispatch via `brouwer_homeo_dispatch` (mirrors the proved
-- `exists_homeomorph_closed_ball_of_convex_compact`): either K is a singleton
-- (fixed point is trivial) or K is homeomorphic to a closed unit ball in
-- `EuclideanSpace ℝ (Fin n)`. Singleton case: f x ∈ K = {x} gives f x = x.
-- Homeo case: delegate to `brouwer_transport_via_homeo`.

theorem s10826 : ∀ {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
  [FiniteDimensional ℝ E] {K : Set E}
  (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K)
  {f : E → E} (hcont : ContinuousOn f K) (hmaps : Set.MapsTo f K K),
  ∃ x ∈ K, f x = x  := by
  intro E _ _ _ K hne hcomp hconv f hcont hmaps
  have h_dispatch := brouwer_homeo_dispatch (E := E) hne hcomp hconv
  rcases h_dispatch with ⟨x, hKx⟩ | ⟨n, φ, _⟩
  · refine ⟨x, ?_, ?_⟩
    · rw [hKx]; exact Set.mem_singleton x
    · have hmem : x ∈ K := by rw [hKx]; exact Set.mem_singleton x
      have hfx : f x ∈ K := hmaps hmem
      rw [hKx, Set.mem_singleton_iff] at hfx
      exact hfx
  · exact brouwer_transport_via_homeo φ hcont hmaps

end Problems.Topology.brouwer_fixed_point

