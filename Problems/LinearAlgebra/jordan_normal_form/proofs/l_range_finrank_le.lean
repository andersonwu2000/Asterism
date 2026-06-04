import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- range_finrank_le: rank-nullity + nilpotent-surjective collapse forces finrank(range N) ≤ m
-- If N were injective (ker = ⊥), finite-dim gives surjective, so N^k surjective;
-- but N^k = 0 maps everything to 0, forcing W trivial → N = 0, contradicting hN0.
-- Hence ker N ≠ ⊥, so finrank(ker N) ≥ 1, and rank-nullity gives the bound.
-- entry_kind: Builder
theorem range_finrank_le
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (hN0 : N ≠ 0) {m : ℕ}
    (hdim : Module.finrank K W ≤ m + 1) :
    Module.finrank K (LinearMap.range N) ≤ m := by
  have hiter_eq_pow : ∀ k : ℕ, (N : W → W) ^[k] = ⇑(N ^ k) := fun k => by
    induction k with
    | zero => ext x; simp
    | succ n ih => ext x; simp [pow_succ, Function.comp, Module.End.mul_apply, ← ih]
  have hker_ne_bot : LinearMap.ker N ≠ ⊥ := by
    intro hbot
    have hinj : Function.Injective N := LinearMap.ker_eq_bot.mp hbot
    have hsurj : Function.Surjective (N : W → W) :=
      LinearMap.injective_iff_surjective.mp hinj
    obtain ⟨k, hk⟩ := hN
    have hpow_surj : Function.Surjective ((N : W → W) ^[k]) := hsurj.iterate k
    rw [hiter_eq_pow, hk] at hpow_surj
    have hsub : ∀ w : W, w = 0 := fun w => by
      obtain ⟨v, hv⟩ := hpow_surj w
      simp [LinearMap.zero_apply] at hv
      exact hv.symm
    exact hN0 (LinearMap.ext (fun x => by simp [hsub x]))
  have hrn : Module.finrank K (LinearMap.range N) + Module.finrank K (LinearMap.ker N) =
      Module.finrank K W := LinearMap.finrank_range_add_finrank_ker N
  have hker_pos : 1 ≤ Module.finrank K (LinearMap.ker N) := by
    rw [Nat.one_le_iff_ne_zero]
    exact fun h => hker_ne_bot (Submodule.finrank_eq_zero.mp h)
  omega

end Problems.LinearAlgebra.jordan_normal_form
