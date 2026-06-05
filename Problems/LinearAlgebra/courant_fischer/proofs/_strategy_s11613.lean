import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- Dimension count: dim(U⊓W)+dim(U⊔W)=dim U+dim W and dim(U⊔W)≤n force dim(U⊓W)>0.
-- Hence U⊓W≠⊥ yields a nonzero vector lying in both U and W. Direct leaf proof.
theorem s11613
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    (U W : Submodule ℝ E) {n : ℕ} (hn : Module.finrank ℝ E = n)
    (h : n < Module.finrank ℝ U + Module.finrank ℝ W) :
    ∃ x : E, x ∈ U ∧ x ∈ W ∧ x ≠ 0  := by
  have hcard : Module.finrank ℝ (U ⊔ W : Submodule ℝ E) + Module.finrank ℝ (U ⊓ W : Submodule ℝ E)
      = Module.finrank ℝ U + Module.finrank ℝ W := Submodule.finrank_sup_add_finrank_inf_eq U W
  have hle : Module.finrank ℝ (U ⊔ W : Submodule ℝ E) ≤ n := hn ▸ Submodule.finrank_le _
  have hpos : 0 < Module.finrank ℝ (U ⊓ W : Submodule ℝ E) := by omega
  have hne : (U ⊓ W : Submodule ℝ E) ≠ ⊥ := by
    intro hbot
    rw [hbot] at hpos
    simp at hpos
  obtain ⟨x, hx, hx0⟩ := Submodule.exists_mem_ne_zero_of_ne_bot hne
  exact ⟨x, (Submodule.mem_inf.mp hx).1, (Submodule.mem_inf.mp hx).2, hx0⟩

end Problems.LinearAlgebra.courant_fischer
