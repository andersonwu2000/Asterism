import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_drop_subsingleton_subtype

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Drop the trivial (out-of-range) summands, then reindex the surviving subtype onto `J`.
-- `drop_subsingleton_subtype` collapses `⨁ I, M` onto the sub-index `{i // i ∈ range f}`
--   (every dropped summand is `Subsingleton`), and `DirectSum.lequivCongrLeft` reindexes
--   that subtype back to `J` via `Equiv.ofInjective f hf`.  The drop lemma is the only real
--   work; the reindex is a direct mathlib citation.
theorem s11583 {R : Type*} [CommRing R]
    {I J : Type*} [Fintype I] [DecidableEq I] [Fintype J] [DecidableEq J]
    (M : I → Type*) [∀ i, AddCommGroup (M i)] [∀ i, Module R (M i)]
    (f : J → I) (hf : Function.Injective f)
    (htriv : ∀ i, (∀ j, f j ≠ i) → Subsingleton (M i)) :
    Nonempty (DirectSum I M ≃ₗ[R] DirectSum J (fun j => M (f j)))  := by
  classical
  obtain ⟨g⟩ := drop_subsingleton_subtype (R := R) M (fun i => i ∈ Set.range f)
    (fun i hi => htriv i (fun j hj => hi ⟨j, hj⟩))
  exact ⟨g.trans (DirectSum.lequivCongrLeft R (Equiv.ofInjective f hf).symm)⟩

end Problems.LinearAlgebra.invariant_factor_decomposition
