import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs.L_iter_shift
import Problems.Minif2f.imo_1987_p4.proofs.L_residue_fixed_point

namespace Problems.Minif2f.imo_1987_p4

-- From f∘f = (·+1987) derive an iterated shift relation, then locate a
-- residue fixed point f(a) ≡ a (mod 1987) (involution on ℤ/1987 is forced
-- to have a fixed point since 1987 is odd). The combinator substitutes
-- f(a) = a + 1987·k into hff(a) via iter_shift, yielding 1 = 2·k → False.
theorem s9487 (f : ℕ → ℕ) : (∀ n, f (f n) = n + 1987) → False  := by
  intro hff
  have h_iter := iter_shift f hff
  obtain ⟨n, k, hnk⟩ := residue_fixed_point f hff
  have hffn : f (f n) = n + 1987 := hff n
  rw [hnk] at hffn
  rw [h_iter] at hffn
  rw [hnk] at hffn
  omega

end Problems.Minif2f.imo_1987_p4
