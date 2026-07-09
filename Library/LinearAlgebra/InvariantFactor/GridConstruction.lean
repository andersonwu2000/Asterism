import Mathlib

/-!
# Grid construction for invariant factor decomposition

This file builds a monotone grid of exponent values used in the invariant factor decomposition.
Starting from a finite type `J` with weights `w : J → ℕ`, it constructs a two-dimensional
array `c : Fin r → Fin s → ℕ` together with an injective index `idx` such that: rows are
monotone column-wise, entries at indexed positions recover the original weights, and all
other entries are zero.
-/

namespace Library.LinearAlgebra.InvariantFactor.GridConstruction

section GridJ

variable {J : Type*} [Fintype J] (w : J → ℕ)

/-- Any finite type `J` with a weight function `w : J → ℕ` admits an enumeration
`e : Fin (Fintype.card J) ≃ J` such that `w ∘ e` is monotone. -/
theorem sorted_enum :
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

/-- Given a weight function `w : J → ℕ` and a row count `r ≥ |J|`, there exist a monotone
vector `cvec : Fin r → ℕ` and an injective placement `pos : J → Fin r` such that `cvec`
agrees with `w` at every placed position, is zero at unoccupied positions, and every row
index in the top `|J|` slots is occupied. -/
theorem column_block (r : ℕ) (hr : Fintype.card J ≤ r) :
    ∃ (cvec : Fin r → ℕ) (pos : J → Fin r),
      Monotone cvec ∧
      Function.Injective pos ∧
      (∀ j, cvec (pos j) = w j) ∧
      (∀ (k : Fin r), (∀ j, pos j ≠ k) → cvec k = 0) ∧
      (∀ (k : Fin r), r - Fintype.card J ≤ (k : ℕ) → ∃ j, pos j = k)  := by
  set n := Fintype.card J with hn
  have h_sorted : ∃ (e : Fin n ≃ J), Monotone (w ∘ e) := sorted_enum w

  obtain ⟨e, he⟩ := h_sorted

  refine ⟨fun k => if h : (k : ℕ) < r - n then 0 else w (e ⟨(k : ℕ) - (r - n), by omega⟩),
          fun j => ⟨r - n + (e.symm j : ℕ), by omega⟩, ?_, ?_, ?_, ?_, ?_⟩
  · intro a b hab
    have hab' : (a : ℕ) ≤ (b : ℕ) := hab
    by_cases ha : (a : ℕ) < r - n
    · simp only [dif_pos ha]; exact Nat.zero_le _
    · have hb : ¬ (b : ℕ) < r - n := by omega
      simp only [dif_neg ha, dif_neg hb]
      apply he
      rw [Fin.le_def]
      simp only
      omega

  · intro a b hab
    simp only [Fin.mk.injEq] at hab
    exact e.symm.injective (Fin.ext (by omega))
  · intro j
    have hpos : ¬ (r - n + (e.symm j : ℕ)) < r - n := by omega
    simp only [dif_neg hpos]
    have hk : (⟨(r - n + (e.symm j : ℕ)) - (r - n), by omega⟩ : Fin n) = e.symm j :=
      Fin.ext (by simp)

    rw [hk, e.apply_symm_apply]
  · intro k hk
    by_cases hklt : (k : ℕ) < r - n
    · simp only [dif_pos hklt]
    · exfalso
      apply hk (e ⟨(k : ℕ) - (r - n), by omega⟩)
      apply Fin.ext
      simp only [Equiv.symm_apply_apply]
      omega
  · intro k hk
    refine ⟨e ⟨(k : ℕ) - (r - n), by omega⟩, ?_⟩
    apply Fin.ext
    simp only [Equiv.symm_apply_apply]
    omega


/-- Given per-column data indexed by `key : J → Fin s` — monotone value vectors `cvec`,
injective placements `pos`, and compatibility conditions — this assembles a global grid
`c : Fin r → Fin s → ℕ` with an injective index `idx : J → Fin r × Fin s` such that rows
are monotone column-wise, indices recover key and weight values, every row has a positive
entry, and unindexed cells are zero. -/
theorem assemble_grid (hw : ∀ j, 0 < w j)
    (s r : ℕ) (key : J → Fin s)
    (cvec : Fin s → Fin r → ℕ)
    (pos : ∀ t : Fin s, {j : J // key j = t} → Fin r)
    (hmono : ∀ t, Monotone (cvec t))
    (hinj : ∀ t, Function.Injective (pos t))
    (hval : ∀ t (j : {j : J // key j = t}), cvec t (pos t j) = w j.val)
    (hpad : ∀ t (k : Fin r), (∀ j, pos t j ≠ k) → cvec t k = 0)
    (hcover : ∀ k : Fin r, ∃ (t : Fin s) (j : {j : J // key j = t}), pos t j = k) :
    ∃ (r' : ℕ) (c : Fin r' → Fin s → ℕ) (idx : J → Fin r' × Fin s),
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      Function.Injective idx ∧
      (∀ i, (idx i).2 = key i) ∧
      (∀ i, c (idx i).1 (idx i).2 = w i) ∧
      (∀ k, ∃ t, 0 < c k t) ∧
      (∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0)  := by
  refine ⟨r, fun i t => cvec t i, fun i => (pos (key i) ⟨i, rfl⟩, key i),
    ?_, ?_, ?_, ?_, ?_, ?_⟩
  · intro i j hij t
    exact hmono t hij
  · -- injectivity, via the injective placement on sigma columns
    have hF : Function.Injective
        (fun p : Σ t : Fin s, {j : J // key j = t} => (pos p.1 p.2, p.1)) := by
      rintro ⟨t, j⟩ ⟨t', j'⟩ h
      simp only [Prod.mk.injEq] at h
      obtain ⟨hp, ht⟩ := h
      subst ht
      rw [hinj t hp]
    intro a b hab
    have : (⟨key a, ⟨a, rfl⟩⟩ : Σ t : Fin s, {j : J // key j = t})
        = ⟨key b, ⟨b, rfl⟩⟩ := hF hab
    exact congrArg (fun p : Σ t : Fin s, {j : J // key j = t} => p.2.1) this
  · intro i
    rfl
  · intro i
    exact hval (key i) ⟨i, rfl⟩
  · intro k
    obtain ⟨t, j, hj⟩ := hcover k
    refine ⟨t, ?_⟩
    change 0 < cvec t k
    rw [← hj, hval t j]
    exact hw j.val
  · intro k t hk
    apply hpad t k
    intro j
    obtain ⟨jv, hjv⟩ := j
    subst hjv
    intro hcon
    exact hk jv (by change (pos (key jv) ⟨jv, rfl⟩, key jv) = (k, key jv); rw [hcon])

end GridJ

/-- Given a finite type `ι` with exponents `e : ι → ℕ` and a key function
`key : {i : ι // 0 < e i} → Fin s` on the nonzero-exponent elements, there exist
a row count `r`, a grid `c : Fin r → Fin s → ℕ`, and an injective index
`idx : {i : ι // 0 < e i} → Fin r × Fin s` such that rows are monotone column-wise,
indexed cells recover the exponent values, every row has a positive entry, and all
unindexed cells are zero. -/
theorem monotone_grid_of_keyed_exponents
    {ι : Type*} [Fintype ι] (e : ι → ℕ) (s : ℕ)
    (key : {i : ι // 0 < e i} → Fin s) :
    ∃ (r : ℕ) (c : Fin r → Fin s → ℕ) (idx : {i : ι // 0 < e i} → Fin r × Fin s),
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      Function.Injective idx ∧
      (∀ i, (idx i).2 = key i) ∧
      (∀ i, c (idx i).1 (idx i).2 = e i.val) ∧
      (∀ k, ∃ t, 0 < c k t) ∧
      (∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0)  := by
  classical
  -- r = the tallest column height; each column gets a monotone, bottom-aligned
  -- value vector + injective row placement from `column_block`, applied fibrewise.
  set m : Fin s → ℕ := fun t => Fintype.card {i : {i // 0 < e i} // key i = t} with hmdef
  set r : ℕ := Finset.univ.sup m with hrdef
  choose cvec pos hmono hinj hval hpad hfill using
    fun t : Fin s =>
      column_block (fun j : {i : {i // 0 < e i} // key i = t} => e j.val.val) r
        (by rw [hrdef]; exact Finset.le_sup (f := m) (Finset.mem_univ t))
  -- every row is occupied: the height-achieving column fills its whole bottom block.
  have hcover : ∀ k : Fin r,
      ∃ (t : Fin s) (j : {i : {i // 0 < e i} // key i = t}), pos t j = k := by
    intro k
    have hrpos : 0 < r := lt_of_le_of_lt (Nat.zero_le _) k.isLt
    have hsne : (Finset.univ : Finset (Fin s)).Nonempty := by
      rcases (Finset.univ : Finset (Fin s)).eq_empty_or_nonempty with he | hne
      · exfalso
        have hr0 : r = 0 := by rw [hrdef, he]; exact Finset.sup_empty
        omega
      · exact hne
    obtain ⟨t, -, htsup⟩ := Finset.exists_mem_eq_sup (Finset.univ : Finset (Fin s)) hsne m
    have hcard : Fintype.card {i : {i // 0 < e i} // key i = t} = r := by
      rw [hrdef]; exact htsup.symm
    obtain ⟨j, hj⟩ := hfill t k (by omega)
    exact ⟨t, j, hj⟩
  -- glue the per-column data into the global grid.
  exact assemble_grid (J := {i // 0 < e i}) (fun i => e i.val) (fun i => i.2)
    s r key cvec pos hmono hinj hval hpad hcover

end Library.LinearAlgebra.InvariantFactor.GridConstruction
