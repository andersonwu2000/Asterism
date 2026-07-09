import Mathlib

/-!
# Direct sum reindexing lemmas for the invariant factor decomposition

This file establishes linear equivalences that reshape direct sums: uncurrying a
doubly-indexed sum, dropping subsingleton summands, and reindexing along an injective
map.  These are the elementary bookkeeping steps used to put a module into invariant
factor normal form.
-/

namespace Library.LinearAlgebra.InvariantFactor.DirectSumBasic

variable {R : Type*} [CommRing R]

/-- The iterated direct sum `⨁ a : α, ⨁ b : β, N a b` is linearly equivalent to the
product-indexed direct sum `⨁ p : α × β, N p.1 p.2`. -/
theorem directsum_prod_uncurry
    {α β : Type*}
    (N : α → β → Type*) [∀ a b, AddCommGroup (N a b)] [∀ a b, Module R (N a b)] :
    Nonempty (DirectSum α (fun a => DirectSum β (fun b => N a b)) ≃ₗ[R]
      DirectSum (α × β) (fun ab => N ab.1 ab.2))  := by
  classical
  exact ⟨(DirectSum.sigmaLcurryEquiv R (δ := fun a (b : β) => N a b)).symm.trans
    (DirectSum.lequivCongrLeft R (Equiv.sigmaEquivProd α β))⟩

/-- If `M i` is a subsingleton for every index `i` not satisfying `P`, then
`⨁ i : I, M i` is linearly equivalent to `⨁ i : {i // P i}, M i`. -/
theorem drop_subsingleton_subtype
    {I : Type*} [Fintype I]
    (M : I → Type*) [∀ i, AddCommGroup (M i)] [∀ i, Module R (M i)]
    (P : I → Prop)
    (htriv : ∀ i, ¬ P i → Subsingleton (M i)) :
    Nonempty (DirectSum I M ≃ₗ[R] DirectSum {i // P i} (fun i => M i.val))  := by
  classical
  classical
  let F : DirectSum I M →ₗ[R] DirectSum {i // P i} (fun i => M i.val) :=
    DirectSum.toModule R I _ (fun i =>
      if h : P i then DirectSum.lof R {i // P i} (fun i => M i.val) ⟨i, h⟩ else 0)
  let G : DirectSum {i // P i} (fun i => M i.val) →ₗ[R] DirectSum I M :=
    DirectSum.toModule R {i // P i} _ (fun j => DirectSum.lof R I M j.val)
  refine ⟨LinearEquiv.ofLinear F G ?_ ?_⟩
  · apply DirectSum.linearMap_ext
    rintro ⟨i, hi⟩
    apply LinearMap.ext
    intro x
    simp only [F, G, LinearMap.comp_apply, DirectSum.toModule_lof, LinearMap.id_apply, dif_pos hi]
  · apply DirectSum.linearMap_ext
    intro i
    apply LinearMap.ext
    intro x
    simp only [LinearMap.comp_apply, LinearMap.id_apply]
    by_cases hi : P i
    · simp only [F, G, DirectSum.toModule_lof, dif_pos hi]
    · have : Subsingleton (M i) := htriv i hi
      rw [Subsingleton.elim x 0]
      simp only [F, G, map_zero]

/-- If `f : J → I` is injective and `M i` is a subsingleton whenever `i` lies outside
the range of `f`, then `⨁ i : I, M i` is linearly equivalent to `⨁ j : J, M (f j)`. -/
theorem reindex_drop_subsingleton
    {I J : Type*} [Fintype I] [Fintype J]
    (M : I → Type*) [∀ i, AddCommGroup (M i)] [∀ i, Module R (M i)]
    (f : J → I) (hf : Function.Injective f)
    (htriv : ∀ i, (∀ j, f j ≠ i) → Subsingleton (M i)) :
    Nonempty (DirectSum I M ≃ₗ[R] DirectSum J (fun j => M (f j)))  := by
  classical
  classical
  obtain ⟨g⟩ := drop_subsingleton_subtype (R := R) M (fun i => i ∈ Set.range f)
    (fun i hi => htriv i (fun j hj => hi ⟨j, hj⟩))
  exact ⟨g.trans (DirectSum.lequivCongrLeft R (Equiv.ofInjective f hf).symm)⟩

/-- The quotient `R ⧸ Submodule.span R {1}` is a subsingleton, since `span R {1} = ⊤`. -/
theorem subsingleton_quot_span_one :
    Subsingleton (R ⧸ Submodule.span R {(1 : R)}) := by rw [show Submodule.span R {(1 : R)} = ⊤ from Ideal.span_singleton_one]; exact @Unique.instSubsingleton _ Submodule.QuotientTop.unique

end Library.LinearAlgebra.InvariantFactor.DirectSumBasic
