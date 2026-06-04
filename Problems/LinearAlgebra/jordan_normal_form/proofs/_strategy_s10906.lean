import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_range_finrank_le
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_range_restrict_nilpotent
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_succ_glue

namespace Problems.LinearAlgebra.jordan_normal_form

-- Strong induction on the dimension bound `n`, kept INLINE (lesson: extracting the
-- succ-step with a `∀ {W'} ih` hypothesis binds a fresh universe `u_3 ≠ u_2`, making `ih`
-- unusable on `↥(range N)`; here the inline `ih` lives in `W`'s universe and applies).
-- Base `n=0`: `Fin (finrank W)` is empty, the claim is vacuous. Succ: if `N = 0` every
-- vector is killed (left disjunct); else descend to `U := range N` — `range_finrank_le`
-- gives `finrank U ≤ m`, `range_restrict_nilpotent` its nilpotency, so `ih` yields a Jordan
-- chain basis of `U`, and `succ_glue` extends/glues it to a basis of `W`.
theorem s10906
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (n : ℕ) (hdim : Module.finrank K W ≤ n) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  induction n generalizing W N hN with
  | zero => exact ⟨Module.finBasis K W, fun j => absurd j.isLt (by omega)⟩
  | succ m ih =>
      by_cases hN0 : N = 0
      · subst hN0
        exact ⟨Module.finBasis K W, fun j => Or.inl rfl⟩
      · have h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N :=
          fun x _ => LinearMap.mem_range_self N x
        have hN' : IsNilpotent (N.restrict h_inv) := range_restrict_nilpotent N hN h_inv
        have hle : Module.finrank K (LinearMap.range N) ≤ m := range_finrank_le N hN hN0 hdim
        obtain ⟨bU, hbU⟩ := ih (N.restrict h_inv) hN' hle
        exact succ_glue N hN hN0 h_inv bU hbU

end Problems.LinearAlgebra.jordan_normal_form
