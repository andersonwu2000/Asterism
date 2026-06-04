import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_fin_offset_block_enum
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_offset_enum_transport

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reduce arbitrary Fintype index `ι` to `Fin (card ι)` via `Fintype.equivFin`, build the
-- lexicographic block enumeration there (`fin_offset_block_enum`), then transport the
-- enumeration + offsets back along the index equiv (`offset_enum_transport`).
theorem s10918 {ι : Type*} [Fintype ι] (k : ι → ℕ) :
    ∃ (e : Fin (∑ s, k s) ≃ Σ s : ι, Fin (k s)) (o : ι → ℕ),
      ∀ p : Fin (∑ s, k s), (p : ℕ) = o (e p).1 + ((e p).2 : ℕ)  := by
  obtain ⟨e, o, he⟩ := fin_offset_block_enum (fun i => k ((Fintype.equivFin ι).symm i))
  exact offset_enum_transport k (Fintype.equivFin ι)
    (fun i => k ((Fintype.equivFin ι).symm i)) (fun _ => rfl) e o he

end Problems.LinearAlgebra.jordan_normal_form
