import Mathlib
import Problems.Logic.hilbert_soundness.Defs

namespace Problems.Logic.hilbert_soundness

open FirstOrder Language

/-- **Soundness** of the Hilbert proof system: every sentence derivable from a
theory `T` is a semantic consequence of `T` (`T ⊨ᵇ φ`). The easy direction of,
and a prerequisite to, Gödel's completeness theorem. -/
theorem main : ∀ {L : Language} {T : L.Theory} {φ : L.Sentence},
    Derivable T φ → T ⊨ᵇ φ := by
  sorry

end Problems.Logic.hilbert_soundness
