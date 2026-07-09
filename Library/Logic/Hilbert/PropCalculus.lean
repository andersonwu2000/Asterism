import Mathlib.Data.Nat.Notation
import Mathlib.Data.Set.Defs

/-!
# Weakening for the Hilbert-style propositional calculus

This file builds a classical propositional Hilbert-style proof system from scratch
(`prop_formula`, `prop_eval`, `prop_derives`) and proves weakening: enlarging the context
of hypotheses preserves derivability.

## Main definitions

* `prop_formula`: propositional formulas built from atoms indexed by `ℕ`, implication,
  and falsum. Negation is not a constructor; it is the derived formula `A.imp bot`.
* `prop_eval`: evaluation of a `prop_formula` under a valuation `v : ℕ → Prop`.
* `prop_derives`: the derivability relation `Γ ⊢ A` of a Hilbert-style calculus with the
  `K`/`S` combinator axioms, double-negation elimination, and modus ponens.

## Main statements

* `prop_weakening`: if `Γ ⊢ A` and `Γ ⊆ Δ`, then `Δ ⊢ A`.
-/

namespace Library.Logic.Hilbert.PropCalculus

/-- Classical propositional formulas built from atoms indexed by `ℕ`, implication (`.imp`),
and falsum (`.bot`). Negation is deliberately not a constructor: it is the derived formula
`A.imp .bot`. -/
inductive prop_formula : Type
  | atom : ℕ → prop_formula
  | imp  : prop_formula → prop_formula → prop_formula
  | bot  : prop_formula

/-- Evaluation of a `prop_formula` under a valuation `v : ℕ → Prop`: an atom holds iff its
valuation holds, `.imp` is object-level implication, and `.bot` is `False`. -/
def prop_eval : (ℕ → Prop) → prop_formula → Prop
  | v, .atom n  => v n
  | v, .imp A B => prop_eval v A → prop_eval v B
  | _, .bot     => False

/-- The derivability relation `Γ ⊢ A` of a Hilbert-style propositional calculus: the
hypothesis rule, the `K`/`S` combinator axioms, double-negation elimination, and modus
ponens. -/
inductive prop_derives : Set prop_formula → prop_formula → Prop
  | hyp   : ∀ {Γ A}, A ∈ Γ → prop_derives Γ A
  | axK   : ∀ {Γ} (A B : prop_formula), prop_derives Γ (A.imp (B.imp A))
  | axS   : ∀ {Γ} (A B C : prop_formula),
      prop_derives Γ ((A.imp (B.imp C)).imp ((A.imp B).imp (A.imp C)))
  | axDNE : ∀ {Γ} (A : prop_formula), prop_derives Γ (((A.imp .bot).imp .bot).imp A)
  | mp    : ∀ {Γ A B}, prop_derives Γ (A.imp B) → prop_derives Γ A → prop_derives Γ B

/-- **Weakening**: if `Γ ⊢ A` and `Γ ⊆ Δ`, then `Δ ⊢ A`. Induction on the derivation,
generalizing `Δ` so the context-inclusion hypothesis re-threads through each case: `hyp`
transports membership along the inclusion, the three axioms are context-free, and `mp`
reuses both induction hypotheses under the same inclusion. -/
theorem prop_weakening {Γ Δ : Set prop_formula} {A : prop_formula} (h : prop_derives Γ A) :
    Γ ⊆ Δ → prop_derives Δ A := by
  induction h generalizing Δ with
  | hyp hmem => intro hsub; exact prop_derives.hyp (hsub hmem)
  | axK A B => intro _; exact prop_derives.axK A B
  | axS A B C => intro _; exact prop_derives.axS A B C
  | axDNE A => intro _; exact prop_derives.axDNE A
  | mp hab ha ihab iha => intro hsub; exact prop_derives.mp (ihab hsub) (iha hsub)

end Library.Logic.Hilbert.PropCalculus
