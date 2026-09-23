import Mathlib
import Problems.Combinatorics.uc_mainline.Defs
import Problems.Combinatorics.uc_mainline.T_projection_accounts
import Problems.Combinatorics.uc_mainline.T_witness_number_deficit
import Problems.Combinatorics.uc_mainline.T_pair_invoice

/-!
# Lemma 5b.3.1 of `uc_minimal_deficit_pair.md` (accounts of the pair projection)

> Fix `x != k`, put `V' = V minus {x, k}`, and let `X, Y, Z, W` be the four
> pattern classes at `(x, k)` read as trace families on `V'` (`X` neither,
> `Y` only `x`, `Z` only `k`, `W` both). The **pair projection** is
>
>     G_2 = pi_{x,k}(F) = X u Y u Z u W  (subsets of V').
>
> For a trace `c in G_2` let `m(c)` be the number of the four classes
> containing `c`, minus one (the number of rows of `F` above `c` that the
> projection merges into one). Write, for any family `H` and coordinate `j`,
> `sigma_j(H) = |H| - 2 d_H(j)`, and let `I'_k` denote the `k`-edge family of
> the single projection `pi_x(F)`:
>
>     I'_k = {c <= V' : c in pi_x(F), c + k in pi_x(F)} = (X u Y) cap (Z u W).
>
> **Lemma 5b.3.1 (accounts of the pair projection).** `G_2` is union-closed,
> contains `0`, and every coordinate of `V'` is active in it. Moreover
>
>     N - |G_2| = sum_c m(c) = |I_x| + |I'_k|,
>     d_F(j) - d_{G_2}(j) = sum_{c ni j} m(c) = d_{I_x}(j) + d_{I'_k}(j)   (j in V'),
>
> and both right-hand sides are symmetric in `x, k`: they also equal
> `|I_k| + |I'_x|` and `d_{I_k}(j) + d_{I'_x}(j)`.

(`uc_minimal_deficit_pair.md`, Section 5b.3.)  `G_2 = pairProj F x k`,
`I_x = edgeTrace F x`, `I'_k = edgeTrace (proj F x) k`; the accounts are stated
additively (`N = |G_2| + |I_x| + |I'_k|`), which is equivalent.
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

-- As in the earlier files of the main line, nothing here needs `[Fintype V]`; the
-- instance is kept in the signatures so that the whole main line shares one context.
set_option linter.unusedSectionVars false

variable {V : Type*} [DecidableEq V] [Fintype V]

/-- The multiplicity `m(c) + 1`: the number of the four pattern classes at
`(x, k)` containing the trace `c`. -/
def classCount (F : Finset (Finset V)) (x k : V) (c : Finset V) : ℕ :=
  (if c ∈ patX F x k then 1 else 0) + (if c ∈ patY F x k then 1 else 0) +
  (if c ∈ patZ F x k then 1 else 0) + (if c ∈ patW F x k then 1 else 0)

/-! ## Helpers -/

/-- Membership in a pattern class `F[P, p]`. -/
theorem mem_patternClass {F : Finset (Finset V)} {P p c : Finset V} :
    c ∈ patternClass F P p ↔ ∃ S ∈ F, S ∩ P = p ∧ S \ P = c := by
  simp only [patternClass, Finset.mem_image, Finset.mem_filter]
  constructor
  · rintro ⟨S, ⟨hS, hint⟩, rfl⟩
    exact ⟨S, hS, hint, rfl⟩
  · rintro ⟨S, hS, hint, rfl⟩
    exact ⟨S, ⟨hS, hint⟩, rfl⟩

/-- Membership in the pair projection. -/
theorem mem_pairProj {F : Finset (Finset V)} {x k : V} {c : Finset V} :
    c ∈ pairProj F x k ↔ ∃ S ∈ F, S \ ({x, k} : Finset V) = c := by
  simp only [pairProj, Finset.mem_image]

/-- A subset of a pair is one of the four subsets of that pair (no `x ≠ k` needed:
for `x = k` the list is redundant, not wrong). -/
theorem subset_pair_cases {s : Finset V} {x k : V} (hs : s ⊆ ({x, k} : Finset V)) :
    s = ∅ ∨ s = {x} ∨ s = {k} ∨ s = {x, k} := by
  have hmem : ∀ a ∈ s, a = x ∨ a = k := by
    intro a ha
    simpa using hs ha
  by_cases hx : x ∈ s <;> by_cases hk : k ∈ s
  · refine Or.inr (Or.inr (Or.inr ?_))
    ext a
    simp only [Finset.mem_insert, Finset.mem_singleton]
    refine ⟨hmem a, ?_⟩
    rintro (rfl | rfl)
    · exact hx
    · exact hk
  · refine Or.inr (Or.inl ?_)
    ext a
    simp only [Finset.mem_singleton]
    constructor
    · intro ha
      rcases hmem a ha with h | rfl
      · exact h
      · exact absurd ha hk
    · rintro rfl
      exact hx
  · refine Or.inr (Or.inr (Or.inl ?_))
    ext a
    simp only [Finset.mem_singleton]
    constructor
    · intro ha
      rcases hmem a ha with rfl | h
      · exact absurd ha hx
      · exact h
    · rintro rfl
      exact hk
  · refine Or.inl (Finset.eq_empty_iff_forall_notMem.mpr ?_)
    intro a ha
    rcases hmem a ha with rfl | rfl
    · exact hx ha
    · exact hk ha

/-- The rows of `F` above a trace `c` with `x, k ∉ c` are exactly the members of
`F` among the four sets `c`, `c + x`, `c + k`, `c + x + k`. -/
theorem filter_sdiff_pair_eq (F : Finset (Finset V)) {x k : V} (hxk : x ≠ k) {c : Finset V}
    (hx : x ∉ c) (hk : k ∉ c) :
    F.filter (fun S => S \ ({x, k} : Finset V) = c)
      = ({c, insert x c, insert k c, insert x (insert k c)} :
          Finset (Finset V)).filter (fun S => S ∈ F) := by
  have hxkc : x ∉ insert k c := by
    simp only [Finset.mem_insert, not_or]
    exact ⟨hxk, hx⟩
  ext S
  simp only [Finset.mem_filter, Finset.mem_insert, Finset.mem_singleton]
  constructor
  · rintro ⟨hS, hsd⟩
    rw [sdiff_pair_eq_erase_erase] at hsd
    refine ⟨?_, hS⟩
    by_cases hxS : x ∈ S <;> by_cases hkS : k ∈ S
    · have h1 : S.erase x = insert k c := by
        rw [← hsd, Finset.insert_erase (Finset.mem_erase.mpr ⟨Ne.symm hxk, hkS⟩)]
      have h2 : S = insert x (insert k c) := by rw [← h1, Finset.insert_erase hxS]
      exact Or.inr (Or.inr (Or.inr h2))
    · have hke : k ∉ S.erase x := fun h => hkS (Finset.mem_of_mem_erase h)
      have h1 : S.erase x = c := by rw [← hsd, Finset.erase_eq_of_notMem hke]
      have h2 : S = insert x c := by rw [← h1, Finset.insert_erase hxS]
      exact Or.inr (Or.inl h2)
    · rw [Finset.erase_eq_of_notMem hxS] at hsd
      have h2 : S = insert k c := by rw [← hsd, Finset.insert_erase hkS]
      exact Or.inr (Or.inr (Or.inl h2))
    · have h2 : S = c := by
        rw [← hsd, Finset.erase_eq_of_notMem hxS, Finset.erase_eq_of_notMem hkS]
      exact Or.inl h2
  · rintro ⟨h4, hS⟩
    refine ⟨hS, ?_⟩
    rw [sdiff_pair_eq_erase_erase]
    rcases h4 with rfl | rfl | rfl | rfl
    · rw [Finset.erase_eq_of_notMem hx, Finset.erase_eq_of_notMem hk]
    · rw [Finset.erase_insert hx, Finset.erase_eq_of_notMem hk]
    · rw [Finset.erase_eq_of_notMem hxkc, Finset.erase_insert hk]
    · rw [Finset.erase_insert hxkc, Finset.erase_insert hk]

/-- The fibre of the pair projection above `c` has exactly `classCount F x k c`
rows. -/
theorem card_filter_sdiff_pair (F : Finset (Finset V)) (x k : V) (hxk : x ≠ k) (c : Finset V) :
    (F.filter (fun S => S \ ({x, k} : Finset V) = c)).card = classCount F x k c := by
  by_cases hx : x ∈ c
  · have hfil : F.filter (fun S => S \ ({x, k} : Finset V) = c) = ∅ := by
      rw [Finset.filter_eq_empty_iff]
      intro S _ hsd
      have hmem : x ∈ S \ ({x, k} : Finset V) := by rw [hsd]; exact hx
      exact (Finset.mem_sdiff.mp hmem).2 (Finset.mem_insert_self x {k})
    have hX : c ∉ patX F x k := fun h => (mem_patX.mp h).2.1 hx
    have hY : c ∉ patY F x k := fun h => ((mem_patY hxk).mp h).1 hx
    have hZ : c ∉ patZ F x k := fun h => ((mem_patZ hxk).mp h).1 hx
    have hW : c ∉ patW F x k := fun h => ((mem_patW hxk).mp h).1 hx
    rw [hfil]
    simp [classCount, hX, hY, hZ, hW]
  · by_cases hk : k ∈ c
    · have hfil : F.filter (fun S => S \ ({x, k} : Finset V) = c) = ∅ := by
        rw [Finset.filter_eq_empty_iff]
        intro S _ hsd
        have hmem : k ∈ S \ ({x, k} : Finset V) := by rw [hsd]; exact hk
        exact (Finset.mem_sdiff.mp hmem).2
          (Finset.mem_insert_of_mem (Finset.mem_singleton_self k))
      have hX : c ∉ patX F x k := fun h => (mem_patX.mp h).2.2 hk
      have hY : c ∉ patY F x k := fun h => ((mem_patY hxk).mp h).2.1 hk
      have hZ : c ∉ patZ F x k := fun h => ((mem_patZ hxk).mp h).2.1 hk
      have hW : c ∉ patW F x k := fun h => ((mem_patW hxk).mp h).2.1 hk
      rw [hfil]
      simp [classCount, hX, hY, hZ, hW]
    · have hxkc : x ∉ insert k c := by
        simp only [Finset.mem_insert, not_or]
        exact ⟨hxk, hx⟩
      have hkxc : k ∉ insert x c := by
        simp only [Finset.mem_insert, not_or]
        exact ⟨Ne.symm hxk, hk⟩
      have h1 : c ∉ ({insert x c, insert k c, insert x (insert k c)} :
          Finset (Finset V)) := by
        simp only [Finset.mem_insert, Finset.mem_singleton, not_or]
        refine ⟨?_, ?_, ?_⟩
        · intro h; rw [h] at hx; exact hx (Finset.mem_insert_self x c)
        · intro h; rw [h] at hk; exact hk (Finset.mem_insert_self k c)
        · intro h; rw [h] at hx; exact hx (Finset.mem_insert_self x _)
      have h2 : insert x c ∉ ({insert k c, insert x (insert k c)} :
          Finset (Finset V)) := by
        simp only [Finset.mem_insert, Finset.mem_singleton, not_or]
        refine ⟨?_, ?_⟩
        · intro h; rw [h] at hkxc; exact hkxc (Finset.mem_insert_self k c)
        · intro h; rw [h] at hkxc
          exact hkxc (Finset.mem_insert_of_mem (Finset.mem_insert_self k c))
      have h3 : insert k c ∉ ({insert x (insert k c)} : Finset (Finset V)) := by
        simp only [Finset.mem_singleton]
        intro h; rw [h] at hxkc; exact hxkc (Finset.mem_insert_self x _)
      have eX : (c ∈ patX F x k) ↔ (c ∈ F) := by rw [mem_patX]; tauto
      have eY : (c ∈ patY F x k) ↔ (insert x c ∈ F) := by rw [mem_patY hxk]; tauto
      have eZ : (c ∈ patZ F x k) ↔ (insert k c ∈ F) := by rw [mem_patZ hxk]; tauto
      have eW : (c ∈ patW F x k) ↔ (insert x (insert k c) ∈ F) := by
        rw [mem_patW hxk]; tauto
      rw [filter_sdiff_pair_eq F hxk hx hk, Finset.card_filter,
        Finset.sum_insert h1, Finset.sum_insert h2, Finset.sum_insert h3,
        Finset.sum_singleton]
      simp only [classCount, eX, eY, eZ, eW]
      ring

/-! ## Lemma 5b.3.1 -/

/-- Lemma 5b.3.1, the identification `G_2 = X ∪ Y ∪ Z ∪ W`. -/
theorem pairProj_eq_union_classes (F : Finset (Finset V)) (x k : V) :
    pairProj F x k = patX F x k ∪ patY F x k ∪ patZ F x k ∪ patW F x k := by
  ext c
  simp only [Finset.mem_union, pairProj, Finset.mem_image, patX, patY, patZ, patW,
    mem_patternClass]
  constructor
  · rintro ⟨S, hS, rfl⟩
    rcases subset_pair_cases
        (show S ∩ ({x, k} : Finset V) ⊆ ({x, k} : Finset V) from Finset.inter_subset_right)
      with h | h | h | h
    · exact Or.inl (Or.inl (Or.inl ⟨S, hS, h, rfl⟩))
    · exact Or.inl (Or.inl (Or.inr ⟨S, hS, h, rfl⟩))
    · exact Or.inl (Or.inr ⟨S, hS, h, rfl⟩)
    · exact Or.inr ⟨S, hS, h, rfl⟩
  · rintro (((⟨S, hS, -, rfl⟩ | ⟨S, hS, -, rfl⟩) | ⟨S, hS, -, rfl⟩) | ⟨S, hS, -, rfl⟩) <;>
      exact ⟨S, hS, rfl⟩

/-- Lemma 5b.3.1, closure clause: `G_2` is union-closed. -/
theorem pairProj_unionClosed (F : Finset (Finset V)) (x k : V) (hF : UnionClosed F) :
    UnionClosed (pairProj F x k) := by
  rw [pairProj_eq_proj_proj]
  exact proj_unionClosed _ _ (proj_unionClosed _ _ hF)

/-- Lemma 5b.3.1, empty-row clause: `∅ ∈ G_2`. -/
theorem pairProj_empty_mem (F : Finset (Finset V)) (x k : V) (h0 : ∅ ∈ F) :
    ∅ ∈ pairProj F x k := by
  rw [pairProj_eq_proj_proj]
  exact proj_empty_mem _ _ (proj_empty_mem _ _ h0)

/-- Lemma 5b.3.1, activity clause: every `j ∈ V'` active in `F` is active in `G_2`. -/
theorem pairProj_active (F : Finset (Finset V)) (x k j : V) (hjx : j ≠ x) (hjk : j ≠ k)
    (ha : Active F j) : Active (pairProj F x k) j := by
  rw [pairProj_eq_proj_proj]
  exact proj_active _ _ _ hjk (proj_active _ _ _ hjx ha)

/-- Lemma 5b.3.1, size account through the multiplicities:
`N = Σ_{c ∈ G_2} (m(c) + 1)`, i.e. `N − |G_2| = Σ_c m(c)`. -/
theorem pairProj_card_sum_classCount (F : Finset (Finset V)) (x k : V) (hxk : x ≠ k) :
    ∑ c ∈ pairProj F x k, classCount F x k c = F.card := by
  rw [Finset.card_eq_sum_card_fiberwise (f := fun S => S \ ({x, k} : Finset V))
    (t := pairProj F x k)
    (fun S hS => mem_pairProj.mpr ⟨S, hS, rfl⟩)]
  exact Finset.sum_congr rfl (fun c _ => (card_filter_sdiff_pair F x k hxk c).symm)

/-- Lemma 5b.3.1, size account: `N − |G_2| = |I_x| + |I'_k|`, in the form
`|G_2| + |I_x| + |I'_k| = N`. -/
theorem pairProj_card_add (F : Finset (Finset V)) (x k : V) (hxk : x ≠ k) :
    (pairProj F x k).card + (edgeTrace F x).card + (edgeTrace (proj F x) k).card = F.card := by
  have h1 := proj_card_add_edgeTrace_card (proj F x) k
  have h2 := proj_card_add_edgeTrace_card F x
  rw [pairProj_eq_proj_proj]
  omega

/-- Lemma 5b.3.1, degree account: `d_F(j) − d_{G_2}(j) = d_{I_x}(j) + d_{I'_k}(j)`
for `j ∈ V'`, in the form `d_{G_2}(j) + d_{I_x}(j) + d_{I'_k}(j) = d_F(j)`. -/
theorem pairProj_deg_add (F : Finset (Finset V)) (x k j : V) (hxk : x ≠ k)
    (hjx : j ≠ x) (hjk : j ≠ k) :
    deg (pairProj F x k) j + deg (edgeTrace F x) j + deg (edgeTrace (proj F x) k) j = deg F j := by
  have h1 := proj_deg_add_edgeTrace_deg (proj F x) k j hjk
  have h2 := proj_deg_add_edgeTrace_deg F x j hjx
  rw [pairProj_eq_proj_proj]
  omega

/-- Lemma 5b.3.1, symmetry of the size account: `|I_x| + |I'_k| = |I_k| + |I'_x|`. -/
theorem pairProj_card_symm (F : Finset (Finset V)) (x k : V) (hxk : x ≠ k) :
    (edgeTrace F x).card + (edgeTrace (proj F x) k).card =
      (edgeTrace F k).card + (edgeTrace (proj F k) x).card := by
  have hcomm : pairProj F k x = pairProj F x k := by
    simp only [pairProj, Finset.pair_comm k x]
  have h1 := pairProj_card_add F x k hxk
  have h2 := pairProj_card_add F k x (Ne.symm hxk)
  rw [hcomm] at h2
  omega

/-- Lemma 5b.3.1, symmetry of the degree account:
`d_{I_x}(j) + d_{I'_k}(j) = d_{I_k}(j) + d_{I'_x}(j)` for `j ∈ V'`. -/
theorem pairProj_deg_symm (F : Finset (Finset V)) (x k j : V) (hxk : x ≠ k)
    (hjx : j ≠ x) (hjk : j ≠ k) :
    deg (edgeTrace F x) j + deg (edgeTrace (proj F x) k) j =
      deg (edgeTrace F k) j + deg (edgeTrace (proj F k) x) j := by
  have hcomm : pairProj F k x = pairProj F x k := by
    simp only [pairProj, Finset.pair_comm k x]
  have h1 := pairProj_deg_add F x k j hxk hjx hjk
  have h2 := pairProj_deg_add F k x j (Ne.symm hxk) hjk hjx
  rw [hcomm] at h2
  omega

#print axioms pairProj_eq_union_classes
#print axioms pairProj_unionClosed
#print axioms pairProj_empty_mem
#print axioms pairProj_active
#print axioms pairProj_card_sum_classCount
#print axioms pairProj_card_add
#print axioms pairProj_deg_add
#print axioms pairProj_card_symm
#print axioms pairProj_deg_symm

end Problems.Combinatorics.uc_mainline
