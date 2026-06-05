import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- exists_subspace_finrank: span of first k+1 basis vectors has finrank k+1,
-- using Module.finBasis + LinearIndependent.comp + finrank_span_eq_card
theorem exists_subspace_finrank
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E]
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ S : Submodule ℝ E, Module.finrank ℝ S = (k : ℕ) + 1 := by
  have hkn : (k : ℕ) + 1 ≤ Module.finrank ℝ E := by rw [hn]; exact k.isLt
  let b := Module.finBasis ℝ E
  let f : Fin ((k : ℕ) + 1) → E := fun i => b ⟨i, Nat.lt_of_lt_of_le i.isLt hkn⟩
  have hinj : Function.Injective (fun i : Fin ((k : ℕ) + 1) =>
      (⟨i.val, Nat.lt_of_lt_of_le i.isLt hkn⟩ : Fin (Module.finrank ℝ E))) := by
    intro a c h
    simp only at h
    have hval : a.val = c.val := by
      have := congrArg (Fin.val (n := Module.finrank ℝ E)) h
      simpa using this
    exact Fin.ext hval
  have hli : LinearIndependent ℝ f := b.linearIndependent.comp _ hinj
  exact ⟨Submodule.span ℝ (Set.range f),
    by rw [finrank_span_eq_card hli, Fintype.card_fin]⟩

end Problems.LinearAlgebra.courant_fischer
