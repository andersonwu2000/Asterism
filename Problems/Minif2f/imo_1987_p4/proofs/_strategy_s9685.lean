import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs.L_odd_involution_fixed
import Problems.Minif2f.imo_1987_p4.proofs.L_residue_involution

namespace Problems.Minif2f.imo_1987_p4

-- σ : Fin 1987 → Fin 1987 with σ(a) = f a % 1987 is an involution (iter_shift slide);
-- since 1987 is odd, σ has a fixed point. Sub 1 = involution property in ℕ form
-- (Builder: iter_shift + Nat.div_add_mod). Sub 2 = pure combinatorial extraction of
-- the fixed point (parity / pairing on Fin 1987), independent of hff.
theorem s9685 (f : ℕ → ℕ) (hff : ∀ n, f (f n) = n + 1987) :
    ∃ a, a < 1987 ∧ f a % 1987 = a := by
  have h_inv := residue_involution f hff
  have h_fp := odd_involution_fixed f hff h_inv
  exact h_fp

end Problems.Minif2f.imo_1987_p4
