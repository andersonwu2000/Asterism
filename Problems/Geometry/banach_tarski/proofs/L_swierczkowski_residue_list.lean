import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Backward
theorem swierczkowski_residue_list
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (L : List (Fin 2 × Bool)) (hred : FreeGroup.reduce L = L) (hL : L ≠ []) :
    ∃ p q r : ℤ,
      List.foldr step (0, 1, 0) L = (p, q, r) ∧
      ¬ (3 ∣ q) ∧
      ( (L.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
        (L.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ) := by sorry

end Problems.Geometry.banach_tarski
