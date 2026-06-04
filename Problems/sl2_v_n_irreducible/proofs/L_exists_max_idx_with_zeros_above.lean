import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- exists_max_idx_with_zeros_above: pick the maximum nonzero-coefficient index
-- in {i ≤ n | c i ≠ 0} via Finset.max'; nonemptiness from _hex; the upper-
-- bound property follows because any larger in-range index would exceed max'.
theorem exists_max_idx_with_zeros_above : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (c : ℕ → R)
    (_hsumne : (∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v) ≠ 0)
    (_hex : ∃ i ≤ n, c i ≠ 0),
  ∃ j ≤ n, c j ≠ 0 ∧ ∀ i, j < i → i ≤ n → c i = 0 := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne c _hsumne _hex
  classical
  let S := (Finset.range (n + 1)).filter (fun i => c i ≠ 0)
  have hSne : S.Nonempty := by
    obtain ⟨i, hi, hci⟩ := _hex
    exact ⟨i, Finset.mem_filter.mpr ⟨Finset.mem_range.mpr (Nat.lt_succ_of_le hi), hci⟩⟩
  refine ⟨S.max' hSne, ?_, ?_, ?_⟩
  · have hjS := Finset.max'_mem S hSne
    exact Nat.lt_succ_iff.mp (Finset.mem_range.mp (Finset.mem_filter.mp hjS).1)
  · exact (Finset.mem_filter.mp (Finset.max'_mem S hSne)).2
  · intro i hij hin
    by_contra hci
    have hiS : i ∈ S :=
      Finset.mem_filter.mpr ⟨Finset.mem_range.mpr (Nat.lt_succ_of_le hin), hci⟩
    have hle := Finset.le_max' S i hiS
    omega

end Problems.sl2_v_n_irreducible
