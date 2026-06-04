import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- sorted_enum: enumerate J in w-monotone order via lex-sort of Fin n by (w ∘ e₀, index)
theorem sorted_enum {J : Type*} [Fintype J] (w : J → ℕ) :
    ∃ (e : Fin (Fintype.card J) ≃ J), Monotone (w ∘ e) := by
  classical
  set n := Fintype.card J
  let e₀ := (Fintype.equivFin J).symm  -- Fin n ≃ J
  -- Lex order on Fin n: first by w ∘ e₀, then by index
  let r : Fin n → Fin n → Prop := fun i j =>
    w (e₀ i) < w (e₀ j) ∨ (w (e₀ i) = w (e₀ j) ∧ i ≤ j)
  haveI hr_dec : DecidableRel r := fun i j => inferInstance
  haveI hr_trans : IsTrans (Fin n) r :=
    ⟨fun a b c h1 h2 => by
      rcases h1 with h1 | ⟨h1, hv1⟩ <;> rcases h2 with h2 | ⟨h2, hv2⟩
      · exact Or.inl (Nat.lt_trans h1 h2)
      · exact Or.inl (h2 ▸ h1)
      · exact Or.inl (h1 ▸ h2)
      · exact Or.inr ⟨h1.trans h2, hv1.trans hv2⟩⟩
  haveI hr_antisymm : Std.Antisymm r :=
    ⟨fun {a b} h1 h2 => by
      rcases h1 with h1 | ⟨h1, hv1⟩ <;> rcases h2 with h2 | ⟨h2, hv2⟩
      · exact absurd (Nat.lt_trans h1 h2) (lt_irrefl _)
      · exact absurd h1 (by omega)
      · exact absurd h2 (by omega)
      · exact Fin.le_antisymm hv1 hv2⟩
  haveI hr_total : Std.Total r :=
    ⟨fun a b => by
      rcases Nat.lt_or_ge (w (e₀ a)) (w (e₀ b)) with h | h
      · exact Or.inl (Or.inl h)
      · rcases Nat.lt_or_ge (w (e₀ b)) (w (e₀ a)) with h2 | h2
        · exact Or.inr (Or.inl h2)
        · have heq : w (e₀ a) = w (e₀ b) := Nat.le_antisymm h2 h
          rcases le_total a b with hv | hv
          · exact Or.inl (Or.inr ⟨heq, hv⟩)
          · exact Or.inr (Or.inr ⟨heq.symm, hv⟩)⟩
  haveI hr_refl : Std.Refl r := ⟨fun a => Or.inr ⟨rfl, le_refl a⟩⟩
  -- Sort univ by r
  set l := (Finset.univ : Finset (Fin n)).sort r with hl_def
  have hl_len : l.length = n := by
    simp only [hl_def, Finset.length_sort, Finset.card_univ, Fintype.card_fin]
  have hl_mem : ∀ x : Fin n, x ∈ l := fun x => by
    simp only [hl_def, Finset.mem_sort]
    exact Finset.mem_univ x
  have hl_nd : l.Nodup := by
    simp only [hl_def]; exact Finset.sort_nodup Finset.univ r
  have hl_pw : l.Pairwise r := by
    simp only [hl_def]; exact Finset.pairwise_sort Finset.univ r
  -- Build equiv Fin n ≃ Fin n from sorted list
  let σ₀ : Fin l.length ≃ Fin n := hl_nd.getEquivOfForallMemList l hl_mem
  let σ : Fin n ≃ Fin n := (finCongr hl_len).symm.trans σ₀
  refine ⟨σ.trans e₀, fun {i j} hij => ?_⟩
  change w (e₀ (σ i)) ≤ w (e₀ (σ j))
  have hle : (finCongr hl_len).symm i ≤ (finCongr hl_len).symm j := by
    simp [Fin.le_iff_val_le_val, hij]
  have hrij : r (σ₀ ((finCongr hl_len).symm i)) (σ₀ ((finCongr hl_len).symm j)) :=
    hl_pw.rel_get_of_le hle
  have hrij' : r (l.get ((finCongr hl_len).symm i)) (l.get ((finCongr hl_len).symm j)) := hrij
  change w (e₀ (l.get ((finCongr hl_len).symm i))) ≤ w (e₀ (l.get ((finCongr hl_len).symm j)))
  rcases hrij' with h | ⟨h, _⟩
  · exact Nat.le_of_lt h
  · exact Nat.le_of_eq h

end Problems.LinearAlgebra.invariant_factor_decomposition
