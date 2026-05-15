import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- max_index_extraction: Finsupp span decomposition + max-support-index extraction,
-- showing w = Σ_{i ≤ m} αᵢ·fⁱ·v with αₘ ≠ 0, by restricting l.support to ≤ n
-- (f^k·v = 0 for k > n by HasPrimitiveVectorWith) and taking the max of that filter.
theorem max_index_extraction
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (w : M) (hwW : w ∈ W) (hwne : w ≠ 0)
    (hwspan : w ∈ Submodule.span R
      (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v))) :
  ∃ m : ℕ, m ≤ n ∧ ∃ α : ℕ → R, α m ≠ 0 ∧
    w = ∑ i ∈ Finset.range (m + 1), α i • ((LieModule.toEnd R L M f) ^ i) v := by
  rw [Finsupp.mem_span_range_iff_exists_finsupp] at hwspan
  obtain ⟨l, hl⟩ := hwspan
  -- f^k·v = 0 for all k > n
  have hfk_zero : ∀ k : ℕ, n < k → (LieModule.toEnd R L M f ^ k) v = 0 := by
    intro k hk
    obtain ⟨d, rfl⟩ := Nat.exists_eq_add_of_lt hk
    induction d with
    | zero =>
      simp only [Nat.add_zero]
      exact hv.pow_toEnd_f_eq_zero_of_eq_nat rfl
    | succ d ih =>
      have hkey : n + (d + 1) + 1 = n + d + 1 + 1 := by omega
      rw [hkey, pow_succ', Module.End.mul_apply, ih (by omega)]
      simp
  -- Restrict l.support to indices ≤ n
  let S := l.support.filter (· ≤ n)
  -- S is nonempty (otherwise w = 0)
  have hSne : S.Nonempty := by
    rw [Finset.nonempty_iff_ne_empty]
    intro hSe
    apply hwne
    rw [← hl, Finsupp.sum]
    apply Finset.sum_eq_zero
    intro k hk
    by_cases hkn : k ≤ n
    · have hkS : k ∈ S := Finset.mem_filter.mpr ⟨hk, hkn⟩
      rw [hSe] at hkS; simp at hkS
    · push Not at hkn
      rw [hfk_zero k hkn]; simp
  let m := S.max' hSne
  have hmS : m ∈ S := Finset.max'_mem S hSne
  have hmn : m ≤ n := (Finset.mem_filter.mp hmS).2
  have hm_supp : m ∈ l.support := (Finset.mem_filter.mp hmS).1
  have hlm : l m ≠ 0 := Finsupp.mem_support_iff.mp hm_supp
  -- S ⊆ Finset.range (m+1)
  have hS_sub : S ⊆ Finset.range (m + 1) := by
    intro k hk
    rw [Finset.mem_range]
    exact Nat.lt_succ_of_le (Finset.le_max' S k hk)
  -- Express w as sum over range (m+1)
  have hw_eq : w = ∑ i ∈ Finset.range (m + 1),
      l i • (LieModule.toEnd R L M f ^ i) v := by
    rw [← hl, Finsupp.sum]
    -- Step 1: drop k > n terms (S = l.support.filter (· ≤ n))
    have step1 : ∑ k ∈ l.support, l k • (LieModule.toEnd R L M f ^ k) v =
        ∑ k ∈ S, l k • (LieModule.toEnd R L M f ^ k) v := by
      symm
      apply Finset.sum_subset (Finset.filter_subset _ l.support)
      intro k hk hkS
      simp only [Finset.mem_filter, hk, true_and, not_le] at hkS
      rw [hfk_zero k hkS]; simp
    -- Step 2: extend from S to range(m+1)
    rw [step1]
    apply Finset.sum_subset hS_sub
    intro k hk hkS
    rw [Finset.mem_range] at hk
    have hkn : k ≤ n := Nat.le_trans (Nat.lt_succ_iff.mp hk) hmn
    have hkl : l k = 0 := by
      by_contra hlk
      exact hkS (Finset.mem_filter.mpr ⟨Finsupp.mem_support_iff.mpr hlk, hkn⟩)
    simp [hkl]
  exact ⟨m, hmn, l, hlm, hw_eq⟩

end Problems.sl2_v_n_irreducible
