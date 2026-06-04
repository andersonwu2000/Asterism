import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_equiv_from_gaps
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gaps_of_starts

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10981 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∃ (p' : ℕ) (l : Fin p' → ℕ) (e : Fin n ≃ Σ t : Fin p', Fin (l t)) (o : Fin p' → ℕ),
      (∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) ∧
      (∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0)) := by
  -- `gaps_of_starts`: turn the ordered start enumeration `g` into block lengths `l : Fin p → ℕ`
  --   (gaps between consecutive starts), with prefix-sum of the first `t` blocks recovering the
  --   `t`-th start, so `S q ↔ q` is some block boundary.
  have h_gaps := gaps_of_starts S h0 p g hmono hrange
  obtain ⟨l, hpos, hsum, hstart⟩ := h_gaps
  -- `block_equiv_from_gaps`: from the gap data build the contiguous-block bijection `e` and
  --   prefix-sum offsets `o`, giving the offset decomposition and the `S q ↔ position-0` alignment.
  have h_equiv := block_equiv_from_gaps S l hpos hsum hstart
  obtain ⟨e, o, ho, halign⟩ := h_equiv
  exact ⟨p, l, e, o, ho, halign⟩

end Problems.LinearAlgebra.jordan_normal_form
