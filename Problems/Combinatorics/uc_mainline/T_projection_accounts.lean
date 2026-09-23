import Mathlib
import Problems.Combinatorics.uc_mainline.Defs

/-!
# Lemma 5b.1 of `uc_minimal_deficit_pair.md` (accounts of the single projection)

> **Lemma 5b.1 (the projection's degrees).** `π_x(F)` is union-closed, contains
> `∅`, every coordinate of `V ∖ {x}` is active in it, `|π_x(F)| = N − |C_x|`,
> and `d_{π_x(F)}(k) = d_F(k) − d_{C_x}(k)` for every `k ≠ x`.

(`uc_minimal_deficit_pair.md`, Section 5b.)  The two accounts are stated in
additive form, which is equivalent because `C_x ⊆ F` and the edge traces
containing `k` are rows containing `k`; the subtractive forms follow.
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

variable {V : Type*} [DecidableEq V] [Fintype V]

-- The accounts of this file are pure `Finset` bookkeeping and never need `[Fintype V]`;
-- the instance is kept in the signatures so that the whole main line shares one context.
set_option linter.unusedSectionVars false

/-! ## Membership in the projection, the slices and the edge traces -/

/-- Unfolding of `deg` as the cardinality of the filter of the rows containing `k`. -/
theorem deg_eq_card_filter (F : Finset (Finset V)) (k : V) :
    deg F k = (F.filter (fun S => k ∈ S)).card := rfl

/-- Membership in `π_x(F)`. -/
theorem mem_proj {F : Finset (Finset V)} {x : V} {c : Finset V} :
    c ∈ proj F x ↔ ∃ S ∈ F, S.erase x = c := by
  simp only [proj, Finset.mem_image]

/-- Membership in `A_x`. -/
theorem mem_zeroSlice {F : Finset (Finset V)} {x : V} {c : Finset V} :
    c ∈ zeroSlice F x ↔ c ∈ F ∧ x ∉ c := by
  simp only [zeroSlice, Finset.mem_filter]

/-- Membership in `B_x`. -/
theorem mem_oneSlice {F : Finset (Finset V)} {x : V} {c : Finset V} :
    c ∈ oneSlice F x ↔ ∃ S ∈ F, x ∈ S ∧ S.erase x = c := by
  simp only [oneSlice, Finset.mem_image, Finset.mem_filter]
  constructor
  · rintro ⟨S, ⟨hS, hxS⟩, h⟩
    exact ⟨S, hS, hxS, h⟩
  · rintro ⟨S, hS, hxS, h⟩
    exact ⟨S, ⟨hS, hxS⟩, h⟩

/-- Membership in `C_x`. -/
theorem mem_edgeTrace {F : Finset (Finset V)} {x : V} {c : Finset V} :
    c ∈ edgeTrace F x ↔ c ∈ F ∧ x ∉ c ∧ insert x c ∈ F := by
  simp only [edgeTrace, Finset.mem_filter]

/-! ## The splitting `π_x(F) = A_x ∪ B_x`, `A_x ∩ B_x = C_x` -/

/-- The projection is the union of the two slices (pair article, Section 5b). -/
theorem proj_eq_zeroSlice_union_oneSlice (F : Finset (Finset V)) (x : V) :
    proj F x = zeroSlice F x ∪ oneSlice F x := by
  ext c
  rw [Finset.mem_union, mem_proj, mem_zeroSlice, mem_oneSlice]
  constructor
  · rintro ⟨S, hS, rfl⟩
    by_cases hx : x ∈ S
    · exact Or.inr ⟨S, hS, hx, rfl⟩
    · refine Or.inl ⟨?_, Finset.notMem_erase _ _⟩
      rwa [Finset.erase_eq_of_notMem hx]
  · rintro (⟨hc, hx⟩ | ⟨S, hS, _, rfl⟩)
    · exact ⟨c, hc, Finset.erase_eq_of_notMem hx⟩
    · exact ⟨S, hS, rfl⟩

/-- The two slices meet exactly in the edge traces: `A_x ∩ B_x = C_x`. -/
theorem zeroSlice_inter_oneSlice (F : Finset (Finset V)) (x : V) :
    zeroSlice F x ∩ oneSlice F x = edgeTrace F x := by
  ext c
  rw [Finset.mem_inter, mem_zeroSlice, mem_oneSlice, mem_edgeTrace]
  constructor
  · rintro ⟨⟨hc, hx⟩, S, hS, hxS, rfl⟩
    refine ⟨hc, hx, ?_⟩
    rwa [Finset.insert_erase hxS]
  · rintro ⟨hc, hx, hins⟩
    exact ⟨⟨hc, hx⟩, insert x c, hins, Finset.mem_insert_self _ _, Finset.erase_insert hx⟩

/-! ## Injectivity of the erasure on the rows containing `x` -/

/-- `S ↦ S ∖ {x}` is injective on any family of rows containing `x`, since
`insert x` inverts it there. -/
theorem erase_injOn_of_mem {G : Finset (Finset V)} {x : V} (hG : ∀ S ∈ G, x ∈ S) :
    Set.InjOn (fun S => Finset.erase S x) ↑G := by
  intro S hS T hT h
  have h' : S.erase x = T.erase x := h
  have h'' : insert x (S.erase x) = insert x (T.erase x) := by rw [h']
  rwa [Finset.insert_erase (hG S (Finset.mem_coe.mp hS)),
    Finset.insert_erase (hG T (Finset.mem_coe.mp hT))] at h''

/-- `|B_x|` equals the number of rows of `F` containing `x`. -/
theorem card_oneSlice (F : Finset (Finset V)) (x : V) :
    (oneSlice F x).card = (F.filter (fun S => x ∈ S)).card := by
  exact Finset.card_image_of_injOn
    (erase_injOn_of_mem (fun _ hS => (Finset.mem_filter.mp hS).2))

/-- For `k ≠ x`, the rows of `B_x` containing `k` are the erasures of the rows of `F`
containing both `x` and `k`. -/
theorem oneSlice_filter_eq_image (F : Finset (Finset V)) (x k : V) (hk : k ≠ x) :
    (oneSlice F x).filter (fun S => k ∈ S)
      = ((F.filter (fun S => x ∈ S)).filter (fun S => k ∈ S)).image
          (fun S => Finset.erase S x) := by
  ext c
  simp only [Finset.mem_filter, mem_oneSlice, Finset.mem_image]
  constructor
  · rintro ⟨⟨S, hS, hxS, rfl⟩, hkc⟩
    exact ⟨S, ⟨⟨hS, hxS⟩, (Finset.mem_erase.mp hkc).2⟩, rfl⟩
  · rintro ⟨S, ⟨⟨hS, hxS⟩, hkS⟩, rfl⟩
    exact ⟨⟨S, hS, hxS, rfl⟩, Finset.mem_erase.mpr ⟨hk, hkS⟩⟩

/-- `d_{B_x}(k) = #{S ∈ F : x ∈ S, k ∈ S}` for `k ≠ x`. -/
theorem card_filter_oneSlice (F : Finset (Finset V)) (x k : V) (hk : k ≠ x) :
    ((oneSlice F x).filter (fun S => k ∈ S)).card
      = ((F.filter (fun S => x ∈ S)).filter (fun S => k ∈ S)).card := by
  rw [oneSlice_filter_eq_image F x k hk]
  exact Finset.card_image_of_injOn
    (erase_injOn_of_mem (fun _ hS => (Finset.mem_filter.mp (Finset.mem_filter.mp hS).1).2))

/-- The row count splits along `x`: `|A_x| + #{S ∈ F : x ∈ S} = N`. -/
theorem card_zeroSlice_add_card_filter (F : Finset (Finset V)) (x : V) :
    (zeroSlice F x).card + (F.filter (fun S => x ∈ S)).card = F.card := by
  rw [zeroSlice, add_comm]
  exact Finset.card_filter_add_card_filter_not (s := F) (fun S => x ∈ S)

/-- The degree count splits along `x`: for any `k`,
`d_{A_x}(k) + #{S ∈ F : x ∈ S, k ∈ S} = d_F(k)`. -/
theorem card_filter_zeroSlice_add_card_filter (F : Finset (Finset V)) (x k : V) :
    ((zeroSlice F x).filter (fun S => k ∈ S)).card
      + ((F.filter (fun S => x ∈ S)).filter (fun S => k ∈ S)).card
      = (F.filter (fun S => k ∈ S)).card := by
  rw [zeroSlice, Finset.filter_comm, Finset.filter_comm (p := fun S => x ∈ S), add_comm]
  exact Finset.card_filter_add_card_filter_not
    (s := F.filter (fun S => k ∈ S)) (fun S => x ∈ S)

/-! ## Lemma 5b.1 -/

/-- Lemma 5b.1, closure clause: `π_x(F)` is union-closed. -/
theorem proj_unionClosed (F : Finset (Finset V)) (x : V) (hF : UnionClosed F) :
    UnionClosed (proj F x) := by
  intro a ha b hb
  rw [mem_proj] at ha hb ⊢
  obtain ⟨S, hS, rfl⟩ := ha
  obtain ⟨T, hT, rfl⟩ := hb
  exact ⟨S ∪ T, hF S hS T hT, Finset.erase_union_distrib S T x⟩

/-- Lemma 5b.1, empty-row clause: `∅ ∈ π_x(F)`. -/
theorem proj_empty_mem (F : Finset (Finset V)) (x : V) (h0 : ∅ ∈ F) :
    ∅ ∈ proj F x := by
  rw [mem_proj]
  exact ⟨∅, h0, by simp⟩

/-- Lemma 5b.1, activity clause: every `k ≠ x` active in `F` is active in `π_x(F)`. -/
theorem proj_active (F : Finset (Finset V)) (x k : V) (hk : k ≠ x) (ha : Active F k) :
    Active (proj F x) k := by
  rw [Active, deg_eq_card_filter, Finset.card_pos] at ha ⊢
  obtain ⟨S, hS⟩ := ha
  rw [Finset.mem_filter] at hS
  exact ⟨S.erase x, Finset.mem_filter.mpr
    ⟨mem_proj.mpr ⟨S, hS.1, rfl⟩, Finset.mem_erase.mpr ⟨hk, hS.2⟩⟩⟩

/-- Lemma 5b.1, size account: `|π_x(F)| = N − |C_x|`, in the form
`|π_x(F)| + |C_x| = N`. -/
theorem proj_card_add_edgeTrace_card (F : Finset (Finset V)) (x : V) :
    (proj F x).card + (edgeTrace F x).card = F.card := by
  rw [proj_eq_zeroSlice_union_oneSlice, ← zeroSlice_inter_oneSlice,
    Finset.card_union_add_card_inter, card_oneSlice]
  exact card_zeroSlice_add_card_filter F x

/-- Lemma 5b.1, size account in the article's subtractive form. -/
theorem proj_card (F : Finset (Finset V)) (x : V) :
    (proj F x).card = F.card - (edgeTrace F x).card := by
  have h := proj_card_add_edgeTrace_card F x
  omega

/-- Lemma 5b.1, degree account: `d_{π_x(F)}(k) = d_F(k) − d_{C_x}(k)` for `k ≠ x`,
in the form `d_{π_x(F)}(k) + d_{C_x}(k) = d_F(k)`. -/
theorem proj_deg_add_edgeTrace_deg (F : Finset (Finset V)) (x k : V) (hk : k ≠ x) :
    deg (proj F x) k + deg (edgeTrace F x) k = deg F k := by
  rw [deg_eq_card_filter, deg_eq_card_filter, deg_eq_card_filter,
    proj_eq_zeroSlice_union_oneSlice, ← zeroSlice_inter_oneSlice,
    Finset.filter_union, Finset.filter_inter_distrib,
    Finset.card_union_add_card_inter, card_filter_oneSlice F x k hk]
  exact card_filter_zeroSlice_add_card_filter F x k

/-- Lemma 5b.1, degree account in the article's subtractive form. -/
theorem proj_deg (F : Finset (Finset V)) (x k : V) (hk : k ≠ x) :
    deg (proj F x) k = deg F k - deg (edgeTrace F x) k := by
  have h := proj_deg_add_edgeTrace_deg F x k hk
  omega

#print axioms proj_unionClosed
#print axioms proj_empty_mem
#print axioms proj_active
#print axioms proj_card_add_edgeTrace_card
#print axioms proj_card
#print axioms proj_deg_add_edgeTrace_deg
#print axioms proj_deg

end Problems.Combinatorics.uc_mainline
