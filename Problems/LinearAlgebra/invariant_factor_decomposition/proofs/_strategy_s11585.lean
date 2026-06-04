import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_assemble_grid
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_column_block

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Decompose the keyed-exponent grid into a per-column sorting lemma and a
-- column-assembly lemma, both abstract over the index type.
--   `column_block` (sub-goal): for any `Fintype J` with weight `w` and a height
--     `r ≥ #J`, sort one column's weights into a monotone, bottom-aligned vector
--     `cvec : Fin r → ℕ` with an injective placement `pos : J → Fin r`, zero
--     padding above the image, and the bottom block `[r - #J, r)` fully filled.
--   `assemble_grid` (sub-goal): given each column's solved `cvec`/`pos` plus a
--     row-coverage hypothesis, glue them into the global grid and discharge all
--     six conjuncts (monotonicity, injectivity, key/value match, no-empty-row,
--     zero-padding) — the sorting is now hypotheses, so only plumbing remains.
-- The combinator picks `r := ⨆ₜ #(column t)`, applies `column_block` fibrewise
-- via `choose`, derives row-coverage `hcover` from the height-achieving column
-- (`Finset.exists_mem_eq_sup` + the bottom-fill guarantee), then hands the
-- per-column data to `assemble_grid`.  Each sub-goal is strictly simpler: the
-- construction (sorting) lives in `column_block`, the bookkeeping in
-- `assemble_grid`, and both drop the parent's `e`-subtype coupling.
theorem s11585
    {ι : Type*} [Fintype ι] (e : ι → ℕ) (s : ℕ)
    (key : {i : ι // 0 < e i} → Fin s) :
    ∃ (r : ℕ) (c : Fin r → Fin s → ℕ) (idx : {i : ι // 0 < e i} → Fin r × Fin s),
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      Function.Injective idx ∧
      (∀ i, (idx i).2 = key i) ∧
      (∀ i, c (idx i).1 (idx i).2 = e i.val) ∧
      (∀ k, ∃ t, 0 < c k t) ∧
      (∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0)  := by
  classical
  -- r = the tallest column height; each column gets a monotone, bottom-aligned
  -- value vector + injective row placement from `column_block`, applied fibrewise.
  set m : Fin s → ℕ := fun t => Fintype.card {i : {i // 0 < e i} // key i = t} with hmdef
  set r : ℕ := Finset.univ.sup m with hrdef
  choose cvec pos hmono hinj hval hpad hfill using
    fun t : Fin s =>
      column_block (fun j : {i : {i // 0 < e i} // key i = t} => e j.val.val) r
        (by rw [hrdef]; exact Finset.le_sup (f := m) (Finset.mem_univ t))
  -- every row is occupied: the height-achieving column fills its whole bottom block.
  have hcover : ∀ k : Fin r,
      ∃ (t : Fin s) (j : {i : {i // 0 < e i} // key i = t}), pos t j = k := by
    intro k
    have hrpos : 0 < r := lt_of_le_of_lt (Nat.zero_le _) k.isLt
    have hsne : (Finset.univ : Finset (Fin s)).Nonempty := by
      rcases (Finset.univ : Finset (Fin s)).eq_empty_or_nonempty with he | hne
      · exfalso
        have hr0 : r = 0 := by rw [hrdef, he]; exact Finset.sup_empty
        omega
      · exact hne
    obtain ⟨t, -, htsup⟩ := Finset.exists_mem_eq_sup (Finset.univ : Finset (Fin s)) hsne m
    have hcard : Fintype.card {i : {i // 0 < e i} // key i = t} = r := by
      rw [hrdef]; exact htsup.symm
    obtain ⟨j, hj⟩ := hfill t k (by omega)
    exact ⟨t, j, hj⟩
  -- glue the per-column data into the global grid.
  exact assemble_grid (J := {i // 0 < e i}) (fun i => e i.val) (fun i => i.2)
    s r key cvec pos hmono hinj hval hpad hcover



end Problems.LinearAlgebra.invariant_factor_decomposition
