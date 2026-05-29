import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_zaxis_collision_angles_per_point_countable
import Problems.Geometry.banach_tarski.proofs.L_good_angle_avoids_zaxis
import Problems.Geometry.banach_tarski.proofs.L_good_angle_avoids_collisions
import Problems.Geometry.banach_tarski.proofs.L_pairwise_disjoint_of_shift_disjoint
import Problems.Geometry.banach_tarski.proofs.L_conj_pairwise_transport
import Problems.Geometry.banach_tarski.proofs.L_zrotation_offaxis_collision_family

namespace Problems.Geometry.banach_tarski

-- Hilbert-hotel disjoint-orbit existence (off-origin), THIN glue over proved bricks.
-- Two sub-goals: (1) zrotation_offaxis_collision_family — a z-rotation isometry family
-- R₀ fixing 0, with the power law, and countable collision-angle sets for every off-axis
-- point; (2) conj_pairwise_transport — transport a pairwise-disjoint orbit through the
-- single conjugation g⁻¹·ρ₀·g.  All the axis-selection and assembly is inline:
--   • get an origin-fixing isometry g moving every p ∈ D off the z-axis, by feeding
--     good_angle_avoids_zaxis the x-rotation family Q (zaxis_collision_angles_per_point_countable);
--     the p ≠ 0 side-condition comes from hD0 (this is where 0 ∉ D is load-bearing);
--   • R₀'s off-axis collision clause then holds on g '' D, so good_angle_avoids_collisions
--     yields a z-rotation ρ₀ with shift-disjoint orbit over g '' D, upgraded to Pairwise by
--     pairwise_disjoint_of_shift_disjoint;
--   • conjugating by g (conj_pairwise_transport) carries Pairwise back to ρ := g⁻¹·ρ₀·g over D,
--     and ρ 0 = 0 since g, ρ₀ both fix 0.
theorem s11454
    (D : Set E) (hD : D.Countable) (hD0 : (0 : E) ∉ D) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧
      Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))  := by
  obtain ⟨R₀, h0₀, hpow₀, hcol₀⟩ := zrotation_offaxis_collision_family
  obtain ⟨Q, hQ0, hQcol⟩ := zaxis_collision_angles_per_point_countable
  obtain ⟨φ, hφ⟩ := good_angle_avoids_zaxis D hD Q
    (fun p hp => hQcol p (by rintro rfl; exact hD0 hp))
  set g : E ≃ᵢ E := Q φ with hg
  have hg0 : g 0 = 0 := hQ0 φ
  have hgoff : ∀ p ∈ D, ¬ ((g p) 0 = 0 ∧ (g p) 1 = 0) := hφ
  have hcolR0 : ∀ p ∈ g '' D, ∀ q ∈ g '' D, {t : ℝ | R₀ t p = q}.Countable := by
    rintro p ⟨p₀, hp₀, rfl⟩ q _
    exact hcol₀ (g p₀) (hgoff p₀ hp₀) q
  obtain ⟨ρ₀, hρ₀0, hshift⟩ :=
    good_angle_avoids_collisions (g '' D) (hD.image g) R₀ h0₀ hpow₀ hcolR0
  have hpair : Pairwise (fun i j : ℕ =>
      Disjoint ((ρ₀ ^ i) '' (g '' D)) ((ρ₀ ^ j) '' (g '' D))) :=
    pairwise_disjoint_of_shift_disjoint ρ₀ (g '' D) hshift
  refine ⟨g⁻¹ * ρ₀ * g, ?_, conj_pairwise_transport g ρ₀ D hpair⟩
  have e1 : (g⁻¹ * ρ₀ * g) 0 = g⁻¹ (ρ₀ (g 0)) := rfl
  rw [e1, hg0, hρ₀0]
  exact (IsometryEquiv.symm_apply_eq g).mpr hg0.symm

end Problems.Geometry.banach_tarski
