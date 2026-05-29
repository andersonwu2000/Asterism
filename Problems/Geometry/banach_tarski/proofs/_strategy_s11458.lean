import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_paradoxical_transfer_along_equidecomp
import Problems.Geometry.banach_tarski.proofs.L_sphere_hilbert_hotel_absorb

namespace Problems.Geometry.banach_tarski

-- Absorb the countable fixed-point set D back into the sphere to upgrade a paradox of S²∖D.
-- (1) sphere_hilbert_hotel_absorb: a Hilbert-hotel rotation makes S² equidecomposable with S²∖D
--     (uses 0∉D and countability of D; an Equidecomp h with source S², target S²∖D).
-- (2) paradoxical_transfer_along_equidecomp: a paradox transfers along equidecomposability —
--     if A ≃ B and B is paradoxical then A is paradoxical (fully abstract over sets, no spheres).
-- Combinator: get h from (1), feed it with the given hp (paradox of S²∖D) into (2). Each sub-goal
-- is strictly simpler — (1) drops the paradox layer, (2) drops all geometry/free-group machinery.
theorem s11458
    (D : Set E) (hDc : D.Countable) (hDs : D ⊆ Metric.sphere (0 : E) 1)
    (hD0 : (0 : E) ∉ D)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = Metric.sphere (0 : E) 1 \ D ∧
        f.target = Metric.sphere (0 : E) 1 \ D ∧
        g.target = Metric.sphere (0 : E) 1 \ D) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 := by
  -- Absorb the countable fixed set D back into S² (S² is equidecomposable with S²∖D
  -- via a Hilbert-hotel rotation: sphere_hilbert_hotel_absorb), then transfer the
  -- paradox of S²∖D back to all of S² (paradoxical_transfer_along_equidecomp).
  obtain ⟨h, hsrc, htgt⟩ := sphere_hilbert_hotel_absorb D hDc hDs hD0
  exact paradoxical_transfer_along_equidecomp _ _ h hsrc htgt hp

end Problems.Geometry.banach_tarski
