import Mathlib
import Problems.Minif2f.amc12a_2003_p1.Defs

namespace Problems.Minif2f.amc12a_2003_p1

-- Direct leaf-bypass (axiom-free): from the closed forms, `u k = v k + 1`
-- pointwise, so the LHS sum exceeds the RHS sum by `card (range 2003) = 2003`.
-- Uses `Finset.sum_add_distrib` + `Finset.sum_const` instead of `native_decide`
-- (the latter introduces a compiler-trust axiom rejected by the framework).
theorem s524 : ∀ (u v : ℕ → ℕ) (h₀ : ∀ n, u n = 2 * n + 2) (h₁ : ∀ n, v n = 2 * n + 1), ((∑ k ∈ Finset.range 2003, u k) - ∑ k ∈ Finset.range 2003, v k) = 2003  := by
  intro u v h₀ h₁
  have key : ∀ k, u k = v k + 1 := fun k => by rw [h₀, h₁]
  have hu : ∑ k ∈ Finset.range 2003, u k
      = (∑ k ∈ Finset.range 2003, v k) + 2003 := by
    have hcongr : ∑ k ∈ Finset.range 2003, u k
        = ∑ k ∈ Finset.range 2003, (v k + 1) :=
      Finset.sum_congr rfl (fun k _ => key k)
    rw [hcongr, Finset.sum_add_distrib, Finset.sum_const, Finset.card_range]
    ring
  omega

end Problems.Minif2f.amc12a_2003_p1
