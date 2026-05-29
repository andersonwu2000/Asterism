import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_orbit_section_general

namespace Problems.Geometry.banach_tarski

-- Drop φ entirely: an orbit section exists for ANY group action.
-- `MulAction.compHom E φ` makes `FreeGroup (Fin 2)` act on `E` by `w • x = φ w • x`
-- (definitionally), so the abstract `orbit_section_general` (rep + word with
-- `wrd x • rep x = x` and `rep` constant on each orbit) specializes directly:
-- the two conjuncts close by `exact h1`/`exact h2` since compHom's `•` is defeq to `φ _ •`.
theorem s11483 (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) :
    ∃ (rep : E → E) (wrd : E → FreeGroup (Fin 2)),
      (∀ x, φ (wrd x) • rep x = x) ∧
      (∀ x (w : FreeGroup (Fin 2)), rep (φ w • x) = rep x)  := by
  letI : MulAction (FreeGroup (Fin 2)) E := MulAction.compHom E φ
  obtain ⟨rep, wrd, h1, h2⟩ :=
    orbit_section_general (G := FreeGroup (Fin 2)) (α := E)
  refine ⟨rep, wrd, ?_, ?_⟩
  · intro x; exact h1 x
  · intro x w; exact h2 x w




end Problems.Geometry.banach_tarski
