import Library.Geometry.BanachTarski.ConeEquidecomp
import Library.Geometry.BanachTarski.ConjugateOrbit
import Library.Geometry.BanachTarski.Defs
import Library.Geometry.BanachTarski.HilbertHotel
import Library.Geometry.BanachTarski.SphereDecomp

open Library.Geometry.BanachTarski.ConeEquidecomp
open Library.Geometry.BanachTarski.ConjugateOrbit
open Library.Geometry.BanachTarski.Defs
open Library.Geometry.BanachTarski.HilbertHotel
open Library.Geometry.BanachTarski.SphereDecomp

/-!
# Ball decomposition for the Banach–Tarski paradox

This file assembles the **Banach–Tarski paradox** for the closed unit ball in a real
inner-product space `E`. The argument is split into three independent transport steps:

1. **Hilbert-hotel absorption** (`ball_origin_absorb_equidecomp`): an off-origin rotation
   with an injective, ball-bounded orbit of `0` supplies an equidecomposition
   `closedBall 0 1 ≃ closedBall 0 1 \ {0}`.
2. **Cone lift** (`punctured_ball_of_origin_fixing_sphere`): a sphere paradox whose
   witnessing isometries all fix the origin lifts radially to a paradoxical decomposition
   of the punctured ball `closedBall 0 1 \ {0}`.
3. **Transfer** (`ball_paradoxical_of_punctured`): the punctured-ball paradox is pulled
   back to a paradox of the full closed ball via the equidecomposition from step 1.

## Main statements

- `ball_origin_absorb_equidecomp`: equidecomposition `closedBall 0 1 ≃ closedBall 0 1 \ {0}`.
- `ball_paradoxical_of_punctured`: punctured-ball paradox implies full-ball paradox.
- `punctured_ball_of_origin_fixing_sphere`: cone lift from sphere to punctured ball.
- `punctured_ball_paradoxical`: `closedBall 0 1 \ {0}` is paradoxical.
- `closedBall_paradoxical`: **the Banach–Tarski paradox** — `closedBall 0 1` admits a
  paradoxical equidecomposition into two disjoint copies of itself.

## Implementation notes

Each theorem corresponds to exactly one transport step, so the proof obligations stay
self-contained and the gluing is explicit.
-/

namespace Library.Geometry.BanachTarski.BallDecomp

/-- There exists an equidecomposition `e` with `e.source = closedBall 0 1` and
`e.target = closedBall 0 1 \ {0}`.

The origin is absorbed via a Hilbert-hotel argument: `bounded_injective_rotation_orbit` supplies
an off-origin isometry $ρ$ whose orbit of $0$ is injective and contained in the closed unit ball,
and `relaxed_hilbert_hotel` (the `D ⊆ A` variant that does not require $ρ(A) ⊆ A$) then yields
the equidecomposition. -/
theorem ball_origin_absorb_equidecomp :
    ∃ e : Equidecomp E (E ≃ᵢ E),
      e.source = Metric.closedBall (0 : E) 1 ∧
      e.target = Metric.closedBall (0 : E) 1 \ {0} := by
  obtain ⟨ρ, hTA, hdisj⟩ := bounded_injective_rotation_orbit
  exact relaxed_hilbert_hotel (Metric.closedBall (0 : E) 1) ({0} : Set E) ρ
    (by simp) hTA hdisj

/-- If the punctured ball `closedBall 0 1 \ {0}` is paradoxical, then the full closed ball
`closedBall 0 1` is paradoxical.

Given `h`, a paradoxical decomposition of `closedBall 0 1 \ {0}`, and the equidecomposition
`closedBall 0 1 ≃ closedBall 0 1 \ {0}` from `ball_origin_absorb_equidecomp`, this follows
from `paradoxical_transfer_along_equidecomp`. -/
theorem ball_paradoxical_of_punctured
    (h : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.closedBall (0 : E) 1 \ {0} ∧
      f.target = Metric.closedBall (0 : E) 1 \ {0} ∧
      g.target = Metric.closedBall (0 : E) 1 \ {0}) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.closedBall (0 : E) 1 ∧
      f.target = Metric.closedBall (0 : E) 1 ∧
      g.target = Metric.closedBall (0 : E) 1 := by
  obtain ⟨e, hsrc, htgt⟩ := ball_origin_absorb_equidecomp
  exact paradoxical_transfer_along_equidecomp
    (Metric.closedBall (0 : E) 1) (Metric.closedBall (0 : E) 1 \ {0}) e hsrc htgt h

/-- Given a sphere paradox `hsph` whose witnessing isometries all fix the origin, construct a
paradoxical decomposition of the punctured ball `closedBall 0 1 \ {0}`.

Each sphere piece is lifted radially via `cone_lift_equidecomp`: since the isometries fix $0$
they commute with scalar multiplication, so the map $y ↦ ‖y‖ · g(‖y‖⁻¹ · y)$ extends each
piece to the cone of its source. The cone of the unit sphere equals the punctured ball
(`cone_over_sphere_eq_punctured_ball`), and `cone_distrib_union` / `cone_preserves_disjoint`
supply the required set-algebra identities. -/
theorem punctured_ball_of_origin_fixing_sphere
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
      g.target = Metric.closedBall (0 : E) 1 \ {0} := by
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

/-- The punctured unit ball `closedBall 0 1 \ {0}` admits a paradoxical equidecomposition.

This follows by applying `punctured_ball_of_origin_fixing_sphere` to
`sphere_paradoxical_origin_fixing`, which provides a sphere paradox witnessed by
origin-fixing isometries (SO(3) rotations fix $0$). -/
theorem punctured_ball_paradoxical : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
    Disjoint f.source g.source ∧
    f.source ∪ g.source = Metric.closedBall (0 : E) 1 \ {0} ∧
    f.target = Metric.closedBall (0 : E) 1 \ {0} ∧
    g.target = Metric.closedBall (0 : E) 1 \ {0} := by
  exact punctured_ball_of_origin_fixing_sphere sphere_paradoxical_origin_fixing

/-- **The Banach–Tarski paradox**: the closed unit ball in `E` admits a paradoxical
equidecomposition, i.e., there exist disjoint equidecomposable pieces `f.source` and
`g.source` that together cover `closedBall 0 1`, and each piece is equidecomposable with
the whole ball.

The proof glues `punctured_ball_paradoxical` (cone lift of the sphere paradox) with
`ball_paradoxical_of_punctured` (origin absorption via a Hilbert-hotel argument). -/
theorem closedBall_paradoxical : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
    Disjoint f.source g.source ∧
    f.source ∪ g.source = Metric.closedBall (0 : E) 1 ∧
    f.target = Metric.closedBall (0 : E) 1 ∧
    g.target = Metric.closedBall (0 : E) 1 := by
  exact ball_paradoxical_of_punctured punctured_ball_paradoxical

end Library.Geometry.BanachTarski.BallDecomp
