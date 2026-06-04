import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- orderemb_succ_le: i-th element of sorted Finset with all elements ≥ 1 is ≥ i+1
-- Proved by Fin.induction using hpos for base case and strict monotonicity for inductive step.
theorem orderemb_succ_le :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    ∀ (s : Finset ℕ) (hcard : s.card = m), (∀ x ∈ s, 1 ≤ x) →
      ∀ i : Fin m, i.val + 1 ≤ (s.orderEmbOfFin hcard i : ℕ) := by
  intro n a _ha _ha0 m _hmn s hcard hpos i
  cases m with
  | zero => exact i.elim0
  | succ m =>
    induction i using Fin.induction with
    | zero =>
      simp only [Fin.val_zero, zero_add]
      exact hpos _ (Finset.orderEmbOfFin_mem s hcard ⟨0, Nat.zero_lt_succ m⟩)
    | succ i ih =>
      have hlt : (s.orderEmbOfFin hcard i.castSucc : ℕ) < s.orderEmbOfFin hcard i.succ := by
        apply (s.orderEmbOfFin hcard).strictMono
        exact @Fin.castSucc_lt_succ _ i
      simp only [Fin.val_succ, Fin.val_castSucc] at *
      omega

end Problems.Minif2f.imo_1978_p5
