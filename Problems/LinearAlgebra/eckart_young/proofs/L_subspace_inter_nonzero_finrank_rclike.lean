import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- Forward rationale: The Eckart–Young lower bound needs the
-- "two subspaces whose dimensions overshoot the ambient dimension meet
-- nonzero" fact over an arbitrary RCLike field, but the Library copy
-- (CourantFischer.SubmoduleLemmas.subspace_inter_nonzero_of_finrank) is
-- stated only over ℝ. This generalizes it to any RCLike 𝕜 inner-product
-- space. The proof is field-agnostic: finrank_sup_add_finrank_inf_eq +
-- omega for 0 < finrank (U ⊓ W), then exists_mem_ne_zero_of_ne_bot.
-- entry_kind: Backward
theorem subspace_inter_nonzero_finrank_rclike {𝕜 : Type*} [RCLike 𝕜]
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (U W : Submodule 𝕜 E) {n : ℕ} (hn : Module.finrank 𝕜 E = n)
    (h : n < Module.finrank 𝕜 U + Module.finrank 𝕜 W) :
    ∃ x : E, x ∈ U ∧ x ∈ W ∧ x ≠ 0 := by
  have hcard : Module.finrank 𝕜 (U ⊔ W : Submodule 𝕜 E) + Module.finrank 𝕜 (U ⊓ W : Submodule 𝕜 E)
      = Module.finrank 𝕜 U + Module.finrank 𝕜 W := Submodule.finrank_sup_add_finrank_inf_eq U W
  have hle : Module.finrank 𝕜 (U ⊔ W : Submodule 𝕜 E) ≤ n := hn ▸ Submodule.finrank_le _
  have hpos : 0 < Module.finrank 𝕜 (U ⊓ W : Submodule 𝕜 E) := by omega
  have hne : (U ⊓ W : Submodule 𝕜 E) ≠ ⊥ := by
    intro hbot
    rw [hbot] at hpos
    simp at hpos
  obtain ⟨x, hx, hx0⟩ := Submodule.exists_mem_ne_zero_of_ne_bot hne
  exact ⟨x, (Submodule.mem_inf.mp hx).1, (Submodule.mem_inf.mp hx).2, hx0⟩

end Problems.LinearAlgebra.eckart_young
