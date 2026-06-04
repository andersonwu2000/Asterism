import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10992 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∀ t : Fin p, (t : ℕ) = 0 → (g t : ℕ) = 0  := by
  intro t ht
  have hn : 0 < n := (g t).pos
  have hSz : S (⟨0, hn⟩ : Fin n) := h0 _ rfl
  obtain ⟨q, hq⟩ := (hrange _).mp hSz
  have htq : t ≤ q := by rw [Fin.le_def]; omega
  have hle : g t ≤ g q := hmono.monotone htq
  rw [hq] at hle
  have : (g t : ℕ) ≤ 0 := hle
  omega

end Problems.LinearAlgebra.jordan_normal_form
