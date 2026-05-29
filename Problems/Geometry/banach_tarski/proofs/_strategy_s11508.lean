import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_exists_free_isometry_embedding
import Problems.Geometry.banach_tarski.proofs.L_fixed_free_action_off_countable
import Problems.Geometry.banach_tarski.proofs.L_paradoxical_of_free_isometry_action_origin_fixing

namespace Problems.Geometry.banach_tarski

-- Origin-fixing strengthening of the Hausdorff→S²∖D paradox (mirror of s11459).
-- Geometric half is cited inline from PROVED bricks: exists_free_isometry_embedding (s11470)
-- gives an injective φ : F₂ ↪ (E≃ᵢE) with the EXTRA datum `∀ w, φ w 0 = 0` (every word is an
-- origin-fixing rotation) plus per-word finite fixed sets; fixed_free_action_off_countable
-- (s11471) takes its countable fixed-point union D ⊆ S² (0∉D), invariant + fixed-point-free off D.
-- The single sub-goal `paradoxical_of_free_isometry_action_origin_fixing` is the abstract lift:
-- it reuses the F₂ two-piece split (cf. s11464) but ADDITIONALLY exposes the realizing Finsets
-- Sf,Sg (shape {1, φ(of i)} / Hilbert-hotel tower of φ(of 1)-powers), all origin-fixing via hfix0.
-- Combinator: obtain D,φ + props inline, feed M := S²∖D and hfix0 to the lift.
-- Strictly simpler: the sub-goal drops ALL sphere/fixed-point geometry (abstract M).
theorem s11508 :
    ∃ D : Set E, D.Countable ∧ D ⊆ Metric.sphere (0 : E) 1 ∧ (0 : E) ∉ D ∧
      ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = Metric.sphere (0 : E) 1 \ D ∧
        f.target = Metric.sphere (0 : E) 1 \ D ∧
        g.target = Metric.sphere (0 : E) 1 \ D ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨φ, hinj, hfix0, hfin⟩ := exists_free_isometry_embedding
  obtain ⟨D, hcount, hsub, h0, hinv, hfree⟩ := fixed_free_action_off_countable φ hfix0 hfin
  exact ⟨D, hcount, hsub, h0,
    paradoxical_of_free_isometry_action_origin_fixing φ hinj
      (Metric.sphere (0 : E) 1 \ D) hinv hfree hfix0⟩


end Problems.Geometry.banach_tarski

