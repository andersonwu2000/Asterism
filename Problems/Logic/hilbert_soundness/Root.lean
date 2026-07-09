import Mathlib
import Problems.Logic.hilbert_soundness.Defs

namespace Problems.Logic.hilbert_soundness

open FirstOrder Language

/-- **Soundness** of the Hilbert proof system: every sentence derivable from a
theory `T` is a semantic consequence of `T` (`T ⊨ᵇ φ`). The easy direction of,
and a prerequisite to, Gödel's completeness theorem. -/
-- main: soundness of the Hilbert calculus — structural induction on Derivable,
-- each axiom case reduces to a propositional tautology via Formula.realize_imp/realize_bot
theorem main : ∀ {L : Language} {T : L.Theory} {φ : L.Sentence},
    Derivable T φ → T ⊨ᵇ φ := by
  intro _ T _ h
  rw [Theory.models_sentence_iff]
  intro M
  induction h with
  | hyp hφ => exact Theory.realize_sentence_of_mem T hφ
  | mp _ _ ih1 ih2 =>
      simp only [Sentence.Realize, Formula.realize_imp] at *
      exact ih1 ih2
  | ax_k => simp only [Sentence.Realize, Formula.realize_imp]; tauto
  | ax_s => simp only [Sentence.Realize, Formula.realize_imp]; tauto
  | ax_dne => simp only [Sentence.Realize, Formula.realize_imp, Formula.realize_bot]; tauto

end Problems.Logic.hilbert_soundness
