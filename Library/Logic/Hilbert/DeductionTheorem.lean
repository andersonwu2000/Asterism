import Library.Logic.Hilbert.PropCalculus

/-!
# The deduction theorem for the Hilbert-style propositional calculus

This file proves the deduction theorem for the Hilbert-style propositional calculus of
`Library.Logic.Hilbert.PropCalculus`: `Γ ∪ {A} ⊢ B` iff `Γ ⊢ A → B`. The forward direction is
the substantial one; it is established by induction on the derivation of `Γ ∪ {A} ⊢ B`, using
two combinator lemmas (`prop_identity`, `prop_add_hyp`) to discharge the base cases and
`prop_imp_dist` to combine the two induction hypotheses in the modus ponens case.

## Main statements

* `prop_identity`: `Γ ⊢ A → A`.
* `prop_add_hyp`: from `Γ ⊢ B` derive `Γ ⊢ A → B`, by adding a redundant hypothesis.
* `prop_imp_dist`: the `axS`-instance distribution of implication over modus ponens.
* `prop_deduction`: the **deduction theorem**: if `Γ ∪ {A} ⊢ B` then `Γ ⊢ A → B`.
-/

open Library.Logic.Hilbert.PropCalculus

namespace Library.Logic.Hilbert.DeductionTheorem

/-- `Γ ⊢ A → A`, for every context `Γ` and formula `A`. -/
theorem prop_identity : ∀ (Γ : Set prop_formula) (A : prop_formula),
    prop_derives Γ (A.imp A) := fun _ A =>
  prop_derives.mp
    (prop_derives.mp (prop_derives.axS A (A.imp A) A) (prop_derives.axK A (A.imp A)))
    (prop_derives.axK A A)

/-- The "add a redundant hypothesis" move of the Hilbert calculus: from `Γ ⊢ B` derive
`Γ ⊢ A → B` via `axK` and modus ponens. The deduction theorem's hyp-in-`Γ` case and every
axiom case collapse to this single generic step, and it is broadly reusable across the
propositional toolkit. -/
theorem prop_add_hyp {Γ : Set prop_formula} {B : prop_formula}
    (A : prop_formula) (h : prop_derives Γ B) : prop_derives Γ (A.imp B) :=
  prop_derives.mp (prop_derives.axK B A) h

/-- The `axS`-instance distribution of implication over modus ponens: `axS A D E : Γ ⊢
(A → (D → E)) → ((A → D) → (A → E))`; two applications of modus ponens with `h1`, `h2` close
it. -/
theorem prop_imp_dist {Γ : Set prop_formula} {A D E : prop_formula}
    (h1 : prop_derives Γ (A.imp (D.imp E))) (h2 : prop_derives Γ (A.imp D)) :
    prop_derives Γ (A.imp E) := by
  exact prop_derives.mp (prop_derives.mp (prop_derives.axS A D E) h1) h2

/-- **Deduction theorem**: if `Γ ∪ {A} ⊢ B` then `Γ ⊢ A → B`. Induction on the derivation of
`insert A Γ ⊢ C`, generalizing the context via the equation `Δ = insert A Γ` so each induction
hypothesis re-threads it. The `hyp` case splits on `C = A` (`prop_identity`) versus `C ∈ Γ`
(`prop_add_hyp` on `hyp`); each axiom case is `prop_add_hyp` on that axiom; the `mp` case
combines the two induction hypotheses via `prop_imp_dist`. -/
theorem prop_deduction {Γ : Set prop_formula} {A B : prop_formula}
    (h : prop_derives (insert A Γ) B) : prop_derives Γ (A.imp B) := by
  have key : ∀ {Δ : Set prop_formula} {C : prop_formula},
      prop_derives Δ C → Δ = insert A Γ → prop_derives Γ (A.imp C) := by
    intro Δ C hd
    induction hd with
    | hyp hmem =>
        intro heq; subst heq; rcases hmem with rfl | hmem
        · exact prop_identity Γ _
        · exact prop_add_hyp A (prop_derives.hyp hmem)
    | axK C D => intro _; exact prop_add_hyp A (prop_derives.axK C D)
    | axS C D E => intro _; exact prop_add_hyp A (prop_derives.axS C D E)
    | axDNE C => intro _; exact prop_add_hyp A (prop_derives.axDNE C)
    | mp h1 h2 ih1 ih2 => intro heq; exact prop_imp_dist (ih1 heq) (ih2 heq)
  exact key h rfl

end Library.Logic.Hilbert.DeductionTheorem
