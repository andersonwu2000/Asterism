import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Conjugate the linear isometry `R` by the translation `x ↦ x - c`.
-- Build the `IsometryEquiv` explicitly: `toFun x = R (x - c) + c`, inverse
-- `y ↦ R.symm (y - c) + c`; the two `left/right_inv` close by `simp`, and the
-- isometry law reduces to `R`'s isometry plus translation-invariance of `edist`
-- (`edist_add_right`/`edist_sub_right`). The pointwise formula then holds by `rfl`.
-- Direct leaf — no sub-goals.
theorem s11518 (R : E ≃ₗᵢ[ℝ] E) (c : E) :
    ∃ ρ : E ≃ᵢ E, ∀ x : E, ρ x = R (x - c) + c  := by
  refine ⟨⟨⟨fun x => R (x - c) + c, fun y => R.symm (y - c) + c, ?_, ?_⟩, ?_⟩, fun x => rfl⟩
  · intro x; simp
  · intro y; simp
  · intro x y
    change edist (R (x - c) + c) (R (y - c) + c) = edist x y
    rw [edist_add_right, R.isometry (x - c) (y - c), edist_sub_right]

end Problems.Geometry.banach_tarski
