import Library.Logic.Hilbert.PropCalculus

open Library.Logic.Hilbert.PropCalculus

/-!
# Soundness of the Hilbert-style propositional calculus

This file proves soundness for the propositional Hilbert-style calculus of
`Library.Logic.Hilbert.PropCalculus`: every derivable formula is semantically valid under
every valuation that satisfies its hypotheses.

## Main statements

* `eval_ax_dne`, `eval_ax_k`, `eval_ax_s`: the axiom schemas of `prop_derives` (classical
  double-negation elimination, and the `K`/`S` combinators) are semantically valid.
* `prop_soundness`: **soundness**. If `Γ ⊢ A` and every formula of `Γ` holds under a
  valuation `v`, then `A` holds under `v`.
-/

namespace Library.Logic.Hilbert.PropSoundness

/-- Double-negation elimination `((A → ⊥) → ⊥) → A` is semantically valid under every
valuation, classically. -/
theorem eval_ax_dne (v : ℕ → Prop) (A : prop_formula) :
    prop_eval v (((A.imp .bot).imp .bot).imp A) := Classical.byContradiction

/-- The `K` axiom schema `A → (B → A)` is semantically valid under every valuation. -/
theorem eval_ax_k (v : ℕ → Prop) (A B : prop_formula) :
    prop_eval v (A.imp (B.imp A)) := (fun a ↦ a) ∘ fun a _ ↦ a

/-- The `S` axiom schema `(A → B → C) → (A → B) → (A → C)` is semantically valid under
every valuation. -/
theorem eval_ax_s (v : ℕ → Prop) (A B C : prop_formula) :
    prop_eval v ((A.imp (B.imp C)).imp ((A.imp B).imp (A.imp C))) := forall_imp

/-- **Soundness**: if `Γ ⊢ A` and every formula of `Γ` holds under a valuation `v`, then `A`
holds under `v`. Induction on the derivation: `hyp` reads off membership in `Γ`, `mp`
applies the two induction hypotheses, and each axiom schema reduces to its semantic
validity lemma (`eval_ax_dne`, `eval_ax_k`, `eval_ax_s`). -/
theorem prop_soundness {Γ : Set prop_formula} {A : prop_formula} (h : prop_derives Γ A)
    (v : ℕ → Prop) (hv : ∀ B ∈ Γ, prop_eval v B) : prop_eval v A := by
  induction h with
  | hyp hA => exact hv _ hA
  | axK A B => exact eval_ax_k v A B
  | axS A B C => exact eval_ax_s v A B C
  | axDNE A => exact eval_ax_dne v A
  | mp _ _ ihab iha => exact ihab iha

end Library.Logic.Hilbert.PropSoundness
