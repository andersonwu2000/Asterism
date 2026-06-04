import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_partition_from_enumeration
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_start_enumeration

namespace Problems.LinearAlgebra.jordan_normal_form

-- Cut `Fin n` at the start set `S` into contiguous blocks, then read off both alignments.
-- `start_enumeration` lists the start indices in strictly-increasing order (`g` with
--   `Set.range g = {q | S q}`); `partition_from_enumeration` turns that ordered list into the
--   block data `(p, l, e, o)` (block t = the gap between consecutive starts) and verifies the
--   offset decomposition + the `S q ↔ position 0` alignment. The first sub-goal is pure Finset
--   enumeration (`orderEmbOfFin`); the second is monotone arithmetic with the start order
--   already discovered — neither re-states the parent.
theorem s10979 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q) :
    ∃ (p : ℕ) (l : Fin p → ℕ) (e : Fin n ≃ Σ t : Fin p, Fin (l t)) (o : Fin p → ℕ),
      (∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) ∧
      (∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0))  := by
  obtain ⟨p, g, hmono, hrange⟩ := start_enumeration S h0
  exact partition_from_enumeration S h0 p g hmono hrange

end Problems.LinearAlgebra.jordan_normal_form
