import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_exists_rotation_pairwise_disjoint_orbit_off_origin
import Problems.Geometry.banach_tarski.proofs.L_equidecomp_hilbert_hotel
import Problems.Geometry.banach_tarski.proofs.L_isometry_fixing_origin_maps_sphere

namespace Problems.Geometry.banach_tarski

-- Hilbert-hotel absorption of the countable set D back into the sphere.
-- Pick a rotation ρ fixing 0 whose orbits ρⁿ''D are pairwise disjoint (cite the
-- proved sibling exists_rotation_pairwise_disjoint_orbit_off_origin); ρ fixes 0,
-- so it maps S² into itself (isometry_fixing_origin_maps_sphere); then the abstract
-- builder equidecomp_hilbert_hotel sends D̃ = ⋃ₙ ρⁿ''D to D̃∖D and fixes the rest,
-- yielding an Equidecomp with source S², target S²∖D. Each sub-goal is strictly
-- simpler: one is a one-line isometry fact, the other a geometry-free, free-group-free,
-- countability-free PartialEquiv/IsDecompOn construction over abstract sets A,D.
theorem s11462
    (D : Set E) (hDc : D.Countable) (hDs : D ⊆ Metric.sphere (0 : E) 1)
    (hD0 : (0 : E) ∉ D) :
    ∃ h : Equidecomp E (E ≃ᵢ E),
      h.source = Metric.sphere (0 : E) 1 ∧ h.target = Metric.sphere (0 : E) 1 \ D  := by
  obtain ⟨ρ, hρ0, hdisj⟩ := exists_rotation_pairwise_disjoint_orbit_off_origin D hDc hD0
  have hρA : ∀ x ∈ Metric.sphere (0 : E) 1, ρ x ∈ Metric.sphere (0 : E) 1 :=
    fun x hx => isometry_fixing_origin_maps_sphere ρ hρ0 x hx
  exact equidecomp_hilbert_hotel (Metric.sphere (0 : E) 1) D ρ hDs hρA hdisj

end Problems.Geometry.banach_tarski
