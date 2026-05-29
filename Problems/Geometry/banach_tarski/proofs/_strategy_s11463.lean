import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_exists_free_isometry_embedding
import Problems.Geometry.banach_tarski.proofs.L_fixed_free_action_off_countable

namespace Problems.Geometry.banach_tarski

-- (A) of the Hausdorff→S²∖D split: build the F₂↪SO(3)↪(E≃ᵢE) embedding φ and take D as
-- its countable fixed-point set on the unit sphere; φ then acts on S²∖D invariantly and
-- fixed-point-freely, with 0∉D since D⊆S².
-- Sub-goal `exists_free_isometry_embedding` (geometry): an injective φ fixing the origin
--   whose every nontrivial word has a FINITE fixed set on S² (the rotation/det-1 bricks).
-- Sub-goal `fixed_free_action_off_countable` (abstract): from such a φ, take D = the
--   union of those fixed sets — countable (FreeGroup Fin 2 is countable + each fiber finite),
--   φ-invariant and fixed-point-free off D — no sphere/free-group geometry left.
-- Combinator: obtain φ from (A), feed it to (B), repackage with the shared φ.
theorem s11463 :
    ∃ (D : Set E) (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)),
      D.Countable ∧ D ⊆ Metric.sphere (0 : E) 1 ∧ (0 : E) ∉ D ∧
      Function.Injective φ ∧
      (∀ (w : FreeGroup (Fin 2)) (x : E),
          x ∈ Metric.sphere (0 : E) 1 \ D → φ w • x ∈ Metric.sphere (0 : E) 1 \ D) ∧
      (∀ (w : FreeGroup (Fin 2)), w ≠ 1 →
          ∀ x ∈ Metric.sphere (0 : E) 1 \ D, φ w • x ≠ x)  := by
  obtain ⟨φ, hinj, hfix0, hfin⟩ := exists_free_isometry_embedding
  obtain ⟨D, hcount, hsub, h0, hinv, hfree⟩ :=
    fixed_free_action_off_countable φ hfix0 hfin
  exact ⟨D, φ, hcount, hsub, h0, hinj, hinv, hfree⟩

end Problems.Geometry.banach_tarski
