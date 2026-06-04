import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_jordan_from_layout
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_consec_block_layout
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_zero_index_is_bottom

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reindex the flat consecutive Jordan basis `bU` of `range N` into chain-blocks.
-- `zero_index_is_bottom`: flat index 0 has no predecessor, so it is a chain bottom —
--   discharges the layout lemma's "first element is a block start" hypothesis.
-- `consec_block_layout`: pure Fin/ℕ combinatorics (no LA) — for any start-predicate `S`
--   on `Fin n` whose minimum is a start, build block sizes `l`, an equiv
--   `e : Fin n ≃ Σ t, Fin (l t)` and offsets `o` with the lex offset formula and the
--   alignment `S q ↔ (e q).2 = 0`. Strictly simpler: abstract, drops all LA structure.
-- `block_jordan_from_layout`: the LA transfer — `d := bU.reindex e` and the flat Jordan
--   property `hbU` push through the offset/alignment facts (case split + omega on indices).
-- Combine: instantiate the layout with `S q := (N.restrict h_inv)(bU q) = 0`, feed to transfer.
theorem s10928
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∃ (p : ℕ) (l : Fin p → ℕ)
      (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N)),
      ∀ (t : Fin p) (j : Fin (l t)),
        (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩  := by
  have h0 := zero_index_is_bottom N h_inv bU hbU
  obtain ⟨p, l, e, o, h_off, h_align⟩ :=
    consec_block_layout (fun q => (N.restrict h_inv) (bU q) = 0) h0
  exact block_jordan_from_layout N h_inv bU hbU p l e o h_off h_align


end Problems.LinearAlgebra.jordan_normal_form
