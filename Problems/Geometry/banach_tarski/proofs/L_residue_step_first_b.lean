import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- residue_step_first_b: Int.ModEq arithmetic — prepending (1,true) preserves ¬3∣q' and the
-- head-keyed mod-3 residue invariant; witnesses p'=3p, q'=q-4r, r'=2q+r satisfy q'≡-r'[3],
-- p'≡0[3]; hhead excludes the (1,false) case that would break divisibility.
theorem residue_step_first_b
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (M : List (Fin 2 × Bool))
    (hhead : M.head? ≠ some (1, false))
    (p q r : ℤ) (hfold : List.foldr step (0, 1, 0) M = (p, q, r)) (hq : ¬ (3 ∣ q))
    (hclass :
      (M.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3])) :
    ∃ p' q' r' : ℤ,
      List.foldr step (0, 1, 0) ((1, true) :: M) = (p', q', r') ∧ ¬ (3 ∣ q') ∧
      ( (((1, true) :: M).head? = some (0, true)  ∧ p' ≡ q'  [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        (((1, true) :: M).head? = some (0, false) ∧ p' ≡ -q' [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        (((1, true) :: M).head? = some (1, true)  ∧ q' ≡ -r' [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ∨
        (((1, true) :: M).head? = some (1, false) ∧ q' ≡ r'  [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ) := by
  obtain ⟨-, -, hstep_b, -⟩ := hstep p q r
  simp only [List.foldr, hfold, hstep_b]
  use 3 * p, q - 4 * r, 2 * q + r
  refine ⟨rfl, ?_, ?_⟩
  · intro hdvd
    apply hq
    rcases hclass with ⟨-, -, hr⟩ | ⟨-, -, hr⟩ | ⟨-, hqr, -⟩ | ⟨hM, -, -⟩
    · obtain ⟨k1, hk1⟩ := Int.modEq_iff_dvd.mp hr
      obtain ⟨k2, hk2⟩ := hdvd
      exact ⟨k2 - 4 * k1, by omega⟩
    · obtain ⟨k1, hk1⟩ := Int.modEq_iff_dvd.mp hr
      obtain ⟨k2, hk2⟩ := hdvd
      exact ⟨k2 - 4 * k1, by omega⟩
    · obtain ⟨k1, hk1⟩ := Int.modEq_iff_dvd.mp hqr
      obtain ⟨k2, hk2⟩ := hdvd
      omega
    · exact absurd hM hhead
  · simp only [List.head?]
    right; right; left
    refine ⟨trivial, Int.modEq_iff_dvd.mpr ?_, Int.modEq_iff_dvd.mpr ?_⟩
    · exact ⟨r - q, by ring⟩
    · exact ⟨-p, by ring⟩

end Problems.Geometry.banach_tarski
