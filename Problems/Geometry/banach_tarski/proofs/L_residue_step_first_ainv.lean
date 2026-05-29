import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- residue_step_first_ainv: inductive step for first-letter aInv (0,false): unfolds foldr via
-- hfold+hstep, witnesses p'=p+2q, q'=-4p+q, r'=3r, closes ¬3∣q' by mod-3 case split on
-- hclass (aInv branch uses p≡-q, b/bInv branches use p≡0), residue relation p'≡-q' always
-- holds by linear arithmetic, r'=3r≡0 trivially; omega closes all arithmetic after Int.ModEq.
-- entry_kind: Builder
theorem residue_step_first_ainv
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (M : List (Fin 2 × Bool))
    (hhead : M.head? ≠ some (0, true))
    (p q r : ℤ) (hfold : List.foldr step (0, 1, 0) M = (p, q, r)) (hq : ¬ (3 ∣ q))
    (hclass :
      (M.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3])) :
    ∃ p' q' r' : ℤ,
      List.foldr step (0, 1, 0) ((0, false) :: M) = (p', q', r') ∧ ¬ (3 ∣ q') ∧
      ( (((0, false) :: M).head? = some (0, true)  ∧ p' ≡ q'  [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        (((0, false) :: M).head? = some (0, false) ∧ p' ≡ -q' [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        (((0, false) :: M).head? = some (1, true)  ∧ q' ≡ -r' [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ∨
        (((0, false) :: M).head? = some (1, false) ∧ q' ≡ r'  [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ) := by
  obtain ⟨-, h0f, -, -⟩ := hstep p q r
  simp only [List.foldr, hfold, h0f]
  refine ⟨p + 2 * q, -4 * p + q, 3 * r, rfl, ?_, ?_⟩
  · rcases hclass with ⟨h, hp, -⟩ | ⟨-, hp, -⟩ | ⟨-, -, hp'⟩ | ⟨-, -, hp'⟩
    · exact absurd h hhead
    · simp only [Int.ModEq] at hp
      rw [Int.dvd_iff_emod_eq_zero] at hq ⊢
      push Not at hq ⊢
      omega
    · simp only [Int.ModEq] at hp'
      rw [Int.dvd_iff_emod_eq_zero] at hq ⊢
      push Not at hq ⊢
      omega
    · simp only [Int.ModEq] at hp'
      rw [Int.dvd_iff_emod_eq_zero] at hq ⊢
      push Not at hq ⊢
      omega
  · right; left; refine ⟨rfl, ?_, ?_⟩ <;> simp [Int.ModEq]; omega

end Problems.Geometry.banach_tarski