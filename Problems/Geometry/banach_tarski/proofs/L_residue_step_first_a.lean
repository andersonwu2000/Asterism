import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- residue_step_first_a: Int.ModEq arithmetic — prepending (0,true) preserves ¬3∣q' and the
-- head-keyed mod-3 residue invariant; witnesses p'=p-2q, q'=4p+q, r'=3r satisfy p'≡q'[3], r'≡0[3].
theorem residue_step_first_a
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (M : List (Fin 2 × Bool))
    (hhead : M.head? ≠ some (0, false))
    (p q r : ℤ) (hfold : List.foldr step (0, 1, 0) M = (p, q, r)) (hq : ¬ (3 ∣ q))
    (hclass :
      (M.head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
      (M.head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3])) :
    ∃ p' q' r' : ℤ,
      List.foldr step (0, 1, 0) ((0, true) :: M) = (p', q', r') ∧ ¬ (3 ∣ q') ∧
      ( (((0, true) :: M).head? = some (0, true)  ∧ p' ≡ q'  [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        (((0, true) :: M).head? = some (0, false) ∧ p' ≡ -q' [ZMOD 3] ∧ r' ≡ 0 [ZMOD 3]) ∨
        (((0, true) :: M).head? = some (1, true)  ∧ q' ≡ -r' [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ∨
        (((0, true) :: M).head? = some (1, false) ∧ q' ≡ r'  [ZMOD 3] ∧ p' ≡ 0 [ZMOD 3]) ) := by
  obtain ⟨hstep_a, -, -, -⟩ := hstep p q r
  simp only [List.foldr, hfold, hstep_a]
  refine ⟨p - 2 * q, 4 * p + q, 3 * r, rfl, ?_, ?_⟩
  · intro hdvd
    apply hq
    rcases hclass with ⟨-, hp, -⟩ | ⟨hM, -, -⟩ | ⟨-, -, hp⟩ | ⟨-, -, hp⟩
    · obtain ⟨k1, hk1⟩ := Int.modEq_iff_dvd.mp hp
      obtain ⟨k2, hk2⟩ := hdvd
      exact ⟨2 * k2 - k1 * 2 + k1, by omega⟩
    · exact absurd hM hhead
    · obtain ⟨k1, hk1⟩ := Int.modEq_iff_dvd.mp hp
      obtain ⟨k2, hk2⟩ := hdvd
      exact ⟨k2, by omega⟩
    · obtain ⟨k1, hk1⟩ := Int.modEq_iff_dvd.mp hp
      obtain ⟨k2, hk2⟩ := hdvd
      exact ⟨k2, by omega⟩
  · left
    refine ⟨rfl, Int.modEq_iff_dvd.mpr ?_, Int.modEq_iff_dvd.mpr ?_⟩
    · exact ⟨p + q, by ring⟩
    · exact ⟨-r, by ring⟩

end Problems.Geometry.banach_tarski
