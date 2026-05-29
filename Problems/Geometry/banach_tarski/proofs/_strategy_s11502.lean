import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_cone_over_sphere_eq_punctured_ball
import Problems.Geometry.banach_tarski.proofs.L_cone_distrib_union
import Problems.Geometry.banach_tarski.proofs.L_cone_lift_equidecomp
import Problems.Geometry.banach_tarski.proofs.L_cone_preserves_disjoint

namespace Problems.Geometry.banach_tarski

-- Cone-lift transport: lift each sphere Equidecomp piece radially to the punctured ball.
-- Each piece's decomposition isometries fix 0, hence commute with radial scaling, so the
-- map y ↦ ‖y‖•(piece(‖y‖⁻¹•y)) extends each piece to the cone of its source. The cone of
-- the unit sphere is the punctured ball (cone_over_sphere_eq_punctured_ball / s11488), so
-- coning the two sphere pieces reassembles the punctured-ball paradox.
-- (1) cone_lift_equidecomp: the abstract single-piece cone functor (origin-fixing ⇒ radial).
-- (2) cone_distrib_union / (3) cone_preserves_disjoint: set-algebra of the cone over a sphere.
theorem s11502
    (hsph : ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.closedBall (0 : E) 1 \ {0} ∧
      f.target = Metric.closedBall (0 : E) 1 \ {0} ∧
      g.target = Metric.closedBall (0 : E) 1 \ {0}  := by
  obtain ⟨f, g, Sf, Sg, hdisj, hunion, hftgt, hgtgt, hfdec, hgdec, hf0, hg0⟩ := hsph
  have hfsrc_sub : f.source ⊆ Metric.sphere (0 : E) 1 := by
    rw [← hunion]; exact Set.subset_union_left
  have hgsrc_sub : g.source ⊆ Metric.sphere (0 : E) 1 := by
    rw [← hunion]; exact Set.subset_union_right
  obtain ⟨F, hFsrc, hFtgt⟩ :=
    cone_lift_equidecomp f Sf hfdec hf0 hfsrc_sub hftgt.subset
  obtain ⟨G, hGsrc, hGtgt⟩ :=
    cone_lift_equidecomp g Sg hgdec hg0 hgsrc_sub hgtgt.subset
  refine ⟨F, G, ?_, ?_, ?_, ?_⟩
  · rw [hFsrc, hGsrc]
    exact cone_preserves_disjoint f.source g.source hfsrc_sub hgsrc_sub hdisj
  · rw [hFsrc, hGsrc, ← cone_distrib_union f.source g.source, hunion]
    exact cone_over_sphere_eq_punctured_ball
  · rw [hFtgt, hftgt]; exact cone_over_sphere_eq_punctured_ball
  · rw [hGtgt, hgtgt]; exact cone_over_sphere_eq_punctured_ball

end Problems.Geometry.banach_tarski
