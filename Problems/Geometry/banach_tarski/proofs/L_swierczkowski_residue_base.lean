import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem swierczkowski_residue_base
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (x : Fin 2 × Bool) :
    ∃ p q r : ℤ,
      List.foldr step (0, 1, 0) [x] = (p, q, r) ∧ ¬ (3 ∣ q) ∧
      ( ([x].head? = some (0, true)  ∧ p ≡ q  [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        ([x].head? = some (0, false) ∧ p ≡ -q [ZMOD 3] ∧ r ≡ 0 [ZMOD 3]) ∨
        ([x].head? = some (1, true)  ∧ q ≡ -r [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ∨
        ([x].head? = some (1, false) ∧ q ≡ r  [ZMOD 3] ∧ p ≡ 0 [ZMOD 3]) ) := by
  obtain ⟨ha, hb, hc, hd⟩ := hstep 0 1 0
  norm_num at ha hb hc hd
  -- Normalize ⟨0/1, ⋯⟩ : Fin 2 to numeral form so ha/hb/hc/hd can fire in simp
  fin_cases x <;>
    simp only [List.foldr, List.head?, Fin.mk_zero, Fin.mk_one, ha, hb, hc, hd] <;>
    exact ⟨_, _, _, rfl, by decide, by decide⟩

end Problems.Geometry.banach_tarski
