import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- topeig_le_subtype_card: the initial segment {i : Fin n | i ≤ k} has cardinality k+1,
-- via Fin.card_Iic after identifying the filter with Finset.Iic k.
theorem topeig_le_subtype_card {n : ℕ} (k : Fin n) :
    Fintype.card {i : Fin n // (i : ℕ) ≤ (k : ℕ)} = (k : ℕ) + 1 := by
  rw [Fintype.card_subtype]
  have h : Finset.univ.filter (fun x : Fin n => (x : ℕ) ≤ (k : ℕ)) = Finset.Iic k := by
    ext x; simp [Finset.mem_Iic]
  rw [h]
  exact Fin.card_Iic k
end Problems.LinearAlgebra.courant_fischer
