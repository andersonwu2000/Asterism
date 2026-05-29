import Mathlib

namespace Problems.Geometry.banach_tarski

/-- The ambient Euclidean space ℝ³ used in the Banach–Tarski statement. -/
abbrev E : Type := EuclideanSpace ℝ (Fin 3)

/-- The self-isometry group of `E = ℝ³` acts on `E` by function application.
    mathlib provides `Group (α ≃ᵢ α)`; this `MulAction` instance bridges to
    `Equidecomp`, whose `IsDecompOn` predicate requires `[SMul G X]`. -/
noncomputable instance : SMul (E ≃ᵢ E) E := ⟨fun g x => g x⟩

noncomputable instance : MulAction (E ≃ᵢ E) E where
  one_smul _ := rfl
  mul_smul _ _ _ := rfl

end Problems.Geometry.banach_tarski
