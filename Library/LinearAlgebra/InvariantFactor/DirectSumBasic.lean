import Mathlib

namespace Library.LinearAlgebra.InvariantFactor.DirectSumBasic

-- Flatten the nested direct sum into a product-indexed one (direct proof, no sub-goals).
-- `sigmaLcurryEquiv.symm` curries `⨁ a ⨁ b N a b` back to the sigma-indexed `⨁ (Σ a, β) N`,
-- then `lequivCongrLeft (Equiv.sigmaEquivProd α β)` reindexes `Σ a:α, β` onto `α × β`;
-- the reindexed family `N (h.symm k).1 (h.symm k).2` is defeq to `N k.1 k.2`.
theorem directsum_prod_uncurry {R : Type*} [CommRing R]
    {α β : Type*} [DecidableEq α] [DecidableEq β]
    (N : α → β → Type*) [∀ a b, AddCommGroup (N a b)] [∀ a b, Module R (N a b)] :
    Nonempty (DirectSum α (fun a => DirectSum β (fun b => N a b)) ≃ₗ[R]
      DirectSum (α × β) (fun ab => N ab.1 ab.2))  := by
  exact ⟨(DirectSum.sigmaLcurryEquiv R (δ := fun a (b : β) => N a b)).symm.trans
    (DirectSum.lequivCongrLeft R (Equiv.sigmaEquivProd α β))⟩

-- Drop the subsingleton (¬P) summands: the inclusion {i//P i} ↪ I induces a linear
-- equivalence because every dropped summand M i is a subsingleton (hence 0).
-- F restricts a sum to its P-components, G includes the subtype components back; the
-- two round-trips close componentwise (toModule_lof), the ¬P case via Subsingleton.elim.
theorem drop_subsingleton_subtype {R : Type*} [CommRing R]
    {I : Type*} [Fintype I] [DecidableEq I]
    (M : I → Type*) [∀ i, AddCommGroup (M i)] [∀ i, Module R (M i)]
    (P : I → Prop) [DecidablePred P]
    (htriv : ∀ i, ¬ P i → Subsingleton (M i)) :
    Nonempty (DirectSum I M ≃ₗ[R] DirectSum {i // P i} (fun i => M i.val))  := by
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

-- Drop the trivial (out-of-range) summands, then reindex the surviving subtype onto `J`.
-- `drop_subsingleton_subtype` collapses `⨁ I, M` onto the sub-index `{i // i ∈ range f}`
--   (every dropped summand is `Subsingleton`), and `DirectSum.lequivCongrLeft` reindexes
--   that subtype back to `J` via `Equiv.ofInjective f hf`.  The drop lemma is the only real
--   work; the reindex is a direct mathlib citation.
theorem reindex_drop_subsingleton {R : Type*} [CommRing R]
    {I J : Type*} [Fintype I] [DecidableEq I] [Fintype J] [DecidableEq J]
    (M : I → Type*) [∀ i, AddCommGroup (M i)] [∀ i, Module R (M i)]
    (f : J → I) (hf : Function.Injective f)
    (htriv : ∀ i, (∀ j, f j ≠ i) → Subsingleton (M i)) :
    Nonempty (DirectSum I M ≃ₗ[R] DirectSum J (fun j => M (f j)))  := by
  classical
  obtain ⟨g⟩ := drop_subsingleton_subtype (R := R) M (fun i => i ∈ Set.range f)
    (fun i hi => htriv i (fun j hj => hi ⟨j, hj⟩))
  exact ⟨g.trans (DirectSum.lequivCongrLeft R (Equiv.ofInjective f hf).symm)⟩

-- entry_kind: Builder
theorem subsingleton_quot_span_one {R : Type*} [CommRing R] :
    Subsingleton (R ⧸ Submodule.span R {(1 : R)}) := by norm_num

end Library.LinearAlgebra.InvariantFactor.DirectSumBasic
