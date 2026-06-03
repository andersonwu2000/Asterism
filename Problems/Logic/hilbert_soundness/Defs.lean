import Mathlib

namespace Problems.Logic.hilbert_soundness

open FirstOrder Language

/-- A Hilbert-style proof relation for first-order sentences over a theory `T`.

mathlib's `ModelTheory` has the full semantic side (`Realize`, `⊨ᵇ`, even the
Compactness Theorem) but NO syntactic derivability relation `⊢`, so the
completeness theorem `T ⊨ φ ↔ T ⊢ φ` cannot even be stated. This supplies the
missing `⊢` as the problem's vocabulary: the classical implicational fragment
(hypotheses, modus ponens, the `K`/`S` combinator axioms, and double-negation
elimination) over first-order sentences. The target theorem (`Root.lean`) is
its **soundness**: everything derivable is a semantic consequence — the easy
half of, and a prerequisite to, Gödel's completeness theorem. -/
inductive Derivable {L : Language} (T : L.Theory) : L.Sentence → Prop
  /-- A member of the theory is derivable. -/
  | hyp {φ : L.Sentence} : φ ∈ T → Derivable T φ
  /-- Modus ponens. -/
  | mp {φ ψ : L.Sentence} :
      Derivable T (φ.imp ψ) → Derivable T φ → Derivable T ψ
  /-- Axiom `K`: `φ → (ψ → φ)`. -/
  | ax_k {φ ψ : L.Sentence} : Derivable T (φ.imp (ψ.imp φ))
  /-- Axiom `S`: `(φ → (ψ → χ)) → ((φ → ψ) → (φ → χ))`. -/
  | ax_s {φ ψ χ : L.Sentence} :
      Derivable T ((φ.imp (ψ.imp χ)).imp ((φ.imp ψ).imp (φ.imp χ)))
  /-- Double-negation elimination (the classical axiom): `¬¬φ → φ`. -/
  | ax_dne {φ : L.Sentence} : Derivable T (((φ.imp ⊥).imp ⊥).imp φ)

end Problems.Logic.hilbert_soundness
