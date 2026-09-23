import Mathlib
import Problems.Combinatorics.uc_mainline.Defs
import Problems.Combinatorics.uc_mainline.T_projection_accounts

/-!
# Lemma 1.1 of `uc_excess_transport.md` (GT1 alone gives the target `(T)`)

Setting of that article (Section 1): `F = A ∪ (B + x)` with `x` tight,
`A = A_x`, `B = B_x`, `s = |A| = |B| = N/2`, `U = ∪ A`; the type of `b ∈ B` is
`m(b) = ∪{a ∈ A : a ⊆ b}`, `μ(D) = #{b : m(b) ∈ D}`, `e(D) = μ(D) − |D|` for
down-closed `D ⊆ A`, and `e* = max_D e(D)` is the Hall deficiency `h(x)`.
For `j ≠ x`, `sp(j) = d_A(j) + d_B(j) − s`; `j` is *abundant* iff `sp(j) > 0`,
*capped* iff `sp(j) ≤ 0`.  The target of the main line, named **GT1**:
**`e* ≥ 1` forces some `j ∈ U` to be abundant.**

> **Lemma 1.1 (GT1 alone gives the target `(T)`).** If every `j != x` is
> capped (`sp(j) <= 0`) then GT1 forces `e* = 0`, i.e. `H = A` is a common fold
> ([tight coordinate 7.2](uc_tight_coordinate.md)).

(`uc_excess_transport.md`, Section 1.)  GT1 is a hypothesis of the lemma, taken
at the instance `(A_x, B_x)`; `e* = hallDef F x`, `U = zeroGround F x`.  The
"i.e." clause is the fold criterion of tight coordinate 7.2 (`e* = 0` iff a
downward bijection `B_x → A_x` exists) and is recorded as the second card.
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

variable {V : Type*} [DecidableEq V] [Fintype V]

/-- The half-surplus `sp(j) = d_A(j) + d_B(j) − s` of the excess-transport
article, with `A = A_x`, `B = B_x`, `s = |A_x|`. -/
def spHalf (F : Finset (Finset V)) (x j : V) : ℤ :=
  (deg (zeroSlice F x) j : ℤ) + (deg (oneSlice F x) j : ℤ) - ((zeroSlice F x).card : ℤ)

/-- Lemma 1.1: if GT1 holds at `x` and every `j ≠ x` is capped, then `e* = 0`. -/
theorem gt1_gives_target (F : Finset (Finset V)) (x : V)
    (hGT1 : 1 ≤ hallDef F x → ∃ j ∈ zeroGround F x, 0 < spHalf F x j)
    (hcap : ∀ j : V, j ≠ x → spHalf F x j ≤ 0) :
    hallDef F x = 0 := by
  by_contra h
  obtain ⟨j, hj, hpos⟩ := hGT1 (by omega)
  simp only [zeroGround, zeroSlice, Finset.mem_biUnion, Finset.mem_filter, id_eq] at hj
  obtain ⟨S, ⟨-, hxS⟩, hjS⟩ := hj
  have hjx : j ≠ x := by rintro rfl; exact hxS hjS
  exact absurd (hcap j hjx) (not_le.mpr hpos)

#print axioms gt1_gives_target


section FoldHelpers


/-- `A_x` inherits union closure from `F`. -/
theorem zeroSlice_unionClosed (F : Finset (Finset V)) (x : V) (hF : UnionClosed F) :
    UnionClosed (zeroSlice F x) := by
  intro a ha b hb
  rw [mem_zeroSlice] at ha hb ⊢
  exact ⟨hF a ha.1 b hb.1, by simp [ha.2, hb.2]⟩

/-- `∅ ∈ A_x` whenever `∅ ∈ F`. -/
theorem zeroSlice_empty_mem (F : Finset (Finset V)) (x : V) (h0 : ∅ ∈ F) :
    ∅ ∈ zeroSlice F x :=
  mem_zeroSlice.mpr ⟨h0, Finset.notMem_empty x⟩

omit [Fintype V] in
/-- A union-closed family containing `∅` is closed under the union of any subfamily. -/
theorem biUnion_mem_of_unionClosed {A : Finset (Finset V)} (hA : UnionClosed A) (h0 : ∅ ∈ A) :
    ∀ G : Finset (Finset V), G ⊆ A → G.biUnion id ∈ A := by
  intro G
  induction G using Finset.induction_on with
  | empty => intro _; simpa using h0
  | @insert a G ha ih =>
      intro hsub
      rw [Finset.biUnion_insert]
      simp only [id_eq]
      exact hA a (hsub (Finset.mem_insert_self a G)) _
        (ih fun s hs => hsub (Finset.mem_insert_of_mem hs))

/-- The type `m(b)` of a row lies in `A_x` (uses union closure and `∅ ∈ F`). -/
theorem rowType_mem_zeroSlice (F : Finset (Finset V)) (x : V) (hF : UnionClosed F)
    (h0 : ∅ ∈ F) (b : Finset V) : rowType F x b ∈ zeroSlice F x :=
  biUnion_mem_of_unionClosed (zeroSlice_unionClosed F x hF) (zeroSlice_empty_mem F x h0) _
    (Finset.filter_subset _ _)

omit [Fintype V] in
/-- `m(b) ⊆ b`. -/
theorem rowType_subset (F : Finset (Finset V)) (x : V) (b : Finset V) : rowType F x b ⊆ b := by
  refine Finset.biUnion_subset.mpr ?_
  intro a ha
  exact (Finset.mem_filter.mp ha).2

/-- `e* = 0` is exactly Hall's condition on the down-closed subfamilies of `A_x`. -/
theorem mu_le_card_of_hallDef_zero {F : Finset (Finset V)} {x : V} (h : hallDef F x = 0)
    {D : Finset (Finset V)} (hD : DownClosedIn (zeroSlice F x) D) : mu F x D ≤ D.card := by
  have hmem : D ∈ (zeroSlice F x).powerset.filter
      (fun D => DownClosedIn (zeroSlice F x) D) :=
    Finset.mem_filter.mpr ⟨Finset.mem_powerset.mpr hD.1, hD⟩
  have h2 : mu F x D - D.card ≤ hallDef F x := by
    unfold hallDef
    exact Finset.le_sup (f := fun D => mu F x D - D.card) hmem
  omega

/-- Tightness at `x` gives `|A_x| = |B_x|`. -/
theorem card_zeroSlice_eq_card_oneSlice (F : Finset (Finset V)) (x : V) (hx : Tight F x) :
    (zeroSlice F x).card = (oneSlice F x).card := by
  have h1 := card_zeroSlice_add_card_filter F x
  have h2 := card_oneSlice F x
  have h3 : (F.card : ℤ) - 2 * ((F.filter (fun S => x ∈ S)).card : ℤ) = 0 := hx
  omega

end FoldHelpers

/-- Lemma 1.1, the "i.e." clause through tight coordinate 7.2: in the article's
setting (`F` union-closed with `∅`, `x` tight) and under the same hypotheses,
`H = A_x` is a common fold (a downward bijection `B_x → A_x`).  The setting
hypotheses are load-bearing: without union closure and `∅ ∈ F` the type `m(b)`
need not lie in `A_x` and `hallDef` undercounts (`notes/gt1_fold_counterexample.lean`,
`F = {{1}, {0, 2}}` on `Fin 3`, `x = 0`). -/
theorem gt1_gives_fold (F : Finset (Finset V)) (x : V) (hF : UnionClosed F) (h0 : ∅ ∈ F)
    (hx : Tight F x)
    (hGT1 : 1 ≤ hallDef F x → ∃ j ∈ zeroGround F x, 0 < spHalf F x j)
    (hcap : ∀ j : V, j ≠ x → spHalf F x j ≤ 0) :
    IsFold F x := by
  have hzero : hallDef F x = 0 := gt1_gives_target F x hGT1 hcap
  have hcardAB : (zeroSlice F x).card = (oneSlice F x).card :=
    card_zeroSlice_eq_card_oneSlice F x hx
  -- Hall's condition for the neighbourhood map `b ↦ {a ∈ A_x : a ⊆ b}`.
  have hhall : ∀ S : Finset {b : Finset V // b ∈ oneSlice F x},
      S.card ≤ (S.biUnion
        (fun b => (zeroSlice F x).filter (fun a => a ⊆ (b : Finset V)))).card := by
    intro S
    set N := S.biUnion (fun b => (zeroSlice F x).filter (fun a => a ⊆ (b : Finset V))) with hN
    have hdc : DownClosedIn (zeroSlice F x) N := by
      constructor
      · intro d hd
        obtain ⟨b, -, hb⟩ := Finset.mem_biUnion.mp hd
        exact (Finset.mem_filter.mp hb).1
      · intro a ha d hd had
        obtain ⟨b, hbS, hb⟩ := Finset.mem_biUnion.mp hd
        exact Finset.mem_biUnion.mpr ⟨b, hbS,
          Finset.mem_filter.mpr ⟨ha, had.trans (Finset.mem_filter.mp hb).2⟩⟩
    have hmu : S.card ≤ mu F x N := by
      unfold mu
      have hss : S.image Subtype.val
          ⊆ (oneSlice F x).filter (fun b => rowType F x b ∈ N) := by
        intro c hc
        obtain ⟨b, hbS, rfl⟩ := Finset.mem_image.mp hc
        refine Finset.mem_filter.mpr ⟨b.2, ?_⟩
        exact Finset.mem_biUnion.mpr ⟨b, hbS, Finset.mem_filter.mpr
          ⟨rowType_mem_zeroSlice F x hF h0 _, rowType_subset F x _⟩⟩
      calc S.card = (S.image Subtype.val).card :=
            (Finset.card_image_of_injective S Subtype.coe_injective).symm
        _ ≤ _ := Finset.card_le_card hss
    have := mu_le_card_of_hallDef_zero hzero hdc
    omega
  obtain ⟨f, hfinj, hf⟩ :=
    (Finset.all_card_le_biUnion_card_iff_exists_injective
      (fun b : {b : Finset V // b ∈ oneSlice F x} =>
        (zeroSlice F x).filter (fun a => a ⊆ (b : Finset V)))).mp hhall
  obtain ⟨β, hβ⟩ : ∃ β : Finset V → Finset V,
      ∀ (b : Finset V) (h : b ∈ oneSlice F x), β b = f ⟨b, h⟩ := by
    classical
    exact ⟨fun b => if h : b ∈ oneSlice F x then f ⟨b, h⟩ else b, fun b h => dif_pos h⟩
  have hmaps : ∀ b ∈ oneSlice F x, β b ∈ zeroSlice F x := by
    intro b hb
    rw [hβ b hb]
    exact (Finset.mem_filter.mp (hf ⟨b, hb⟩)).1
  have hsubs : ∀ b ∈ oneSlice F x, β b ⊆ b := by
    intro b hb
    rw [hβ b hb]
    exact (Finset.mem_filter.mp (hf ⟨b, hb⟩)).2
  have hinj : Set.InjOn β ↑(oneSlice F x) := by
    intro b1 h1 b2 h2 heq
    rw [hβ b1 (Finset.mem_coe.mp h1), hβ b2 (Finset.mem_coe.mp h2)] at heq
    exact congrArg Subtype.val (hfinj heq)
  have himg : (oneSlice F x).image β = zeroSlice F x := by
    refine Finset.eq_of_subset_of_card_le ?_ ?_
    · intro c hc
      obtain ⟨b, hb, rfl⟩ := Finset.mem_image.mp hc
      exact hmaps b hb
    · rw [Finset.card_image_of_injOn hinj]
      omega
  refine ⟨β, ⟨hmaps, hinj, ?_⟩, hsubs⟩
  intro a ha
  rw [← himg] at ha
  obtain ⟨b, hb, rfl⟩ := Finset.mem_image.mp (Finset.mem_coe.mp ha)
  exact ⟨b, hb, rfl⟩

#print axioms gt1_gives_fold

end Problems.Combinatorics.uc_mainline
