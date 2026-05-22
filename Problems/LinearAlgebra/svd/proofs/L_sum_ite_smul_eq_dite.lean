import Mathlib
import Problems.LinearAlgebra.svd.Defs

namespace Problems.LinearAlgebra.svd

-- entry_kind: Builder
-- sum_ite_smul_eq_dite: collapse indicator-shaped Finset.sum to dite by Finset.sum_eq_single
theorem sum_ite_smul_eq_dite : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F)
  (i : Fin (Module.finrank 𝕜 E)),
    (∑ j : Fin (Module.finrank 𝕜 F),
      (if (j : ℕ) = (i : ℕ) then ((T.singularValues i : ℝ) : 𝕜) else 0) • b_F j) =
    if h : (i : ℕ) < (Module.finrank 𝕜 F)
    then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
    else 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner b_F i
  split_ifs with h
  · rw [Finset.sum_eq_single ⟨(i : ℕ), h⟩]
    · simp
    · intro j _ hj
      have hne : (j : ℕ) ≠ (i : ℕ) := fun heq => hj (Fin.ext heq)
      simp [hne]
    · intro hmem
      exact absurd (Finset.mem_univ _) hmem
  · apply Finset.sum_eq_zero
    intro j _
    have hne : (j : ℕ) ≠ (i : ℕ) :=
      Nat.ne_of_lt (j.isLt.trans_le (Nat.le_of_not_lt h))
    simp [hne]


end Problems.LinearAlgebra.svd
