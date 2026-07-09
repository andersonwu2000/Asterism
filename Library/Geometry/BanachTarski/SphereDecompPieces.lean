import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.Order.BourbakiWitt
import Mathlib.Order.CompletePartialOrder
import Library.Geometry.BanachTarski.Defs

/-!
# Sphere decomposition pieces for the Banach–Tarski paradox

This file establishes the set-theoretic and word-combinatorial lemmas that carve a
`FreeGroup (Fin 2)`-equivariant orbit set $M$ into the four Banach–Tarski pieces.

## Main statements

* `letter0_partial_equiv_laws` — the four `PartialEquiv` compatibility laws for the
  letter-0 piece.
* `letter0_pieces_disjoint`, `b_letter_pieces_disjoint` — disjointness of the
  positive/negative pieces for each generator.
* `letter0_source_eq_union`, `letter1_source_eq_diff` — set decompositions of the
  letter-0 and letter-1 source sets.
* `b_letter_split`, `letter0_split` — the key equivariance identities transporting the
  free-group relation $a \cdot W_a^{-1} = F_2 \setminus W_a$ to point sets.
-/

open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.SphereDecompPieces

/-- The four `PartialEquiv` compatibility laws for the letter-0 piece.

Given sets $A$, $B$, $M$ with $A \subseteq M$, $A \cap B = \emptyset$, and
$g_0 \cdot B = M \setminus A$, the maps $f$ (identity on $A$, $g_0$-shift off $A$) and
$g$ (identity on $A$, $g_0^{-1}$-shift off $A$) satisfy: $f$ maps $A \cup B$ into $M$,
$g$ maps $M$ into $A \cup B$, $g \circ f = \mathrm{id}$ on $A \cup B$, and
$f \circ g = \mathrm{id}$ on $M$. -/
theorem letter0_partial_equiv_laws
    (A B M : Set E) (g0 : E ≃ᵢ E) (f g : E → E)
    (hAM : A ⊆ M)
    (hAB : Disjoint A B)
    (hsplit : (fun x => g0 • x) '' B = M \ A)
    (hfA : ∀ x ∈ A, f x = x)
    (hfnA : ∀ x, x ∉ A → f x = g0 • x)
    (hgA : ∀ y ∈ A, g y = y)
    (hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y) :
    (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y) := by
  have hBnA : ∀ x ∈ B, x ∉ A := fun x hx => (Set.disjoint_right.mp hAB) hx
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro x hx
    rcases hx with hx | hx
    · rw [hfA x hx]; exact hAM hx
    · rw [hfnA x (hBnA x hx)]
      have h : g0 • x ∈ M \ A := by rw [← hsplit]; exact ⟨x, hx, rfl⟩
      exact h.1
  · intro y hy
    by_cases hyA : y ∈ A
    · rw [hgA y hyA]; exact Or.inl hyA
    · rw [hgnA y hyA]
      have hyMA : y ∈ M \ A := ⟨hy, hyA⟩
      rw [← hsplit] at hyMA
      obtain ⟨b, hb, hbeq⟩ := hyMA
      refine Or.inr ?_
      have : g0⁻¹ • y = b := by rw [← hbeq]; simp
      rw [this]; exact hb
  · intro x hx
    rcases hx with hx | hx
    · rw [hfA x hx, hgA x hx]
    · rw [hfnA x (hBnA x hx)]
      have h : g0 • x ∈ M \ A := by rw [← hsplit]; exact ⟨x, hx, rfl⟩
      rw [hgnA (g0 • x) h.2]; simp
  · intro y hy
    by_cases hyA : y ∈ A
    · rw [hgA y hyA, hfA y hyA]
    · rw [hgnA y hyA]
      have hyMA : y ∈ M \ A := ⟨hy, hyA⟩
      rw [← hsplit] at hyMA
      obtain ⟨b, hb, hbeq⟩ := hyMA
      have hinv : g0⁻¹ • y = b := by rw [← hbeq]; simp
      rw [hinv, hfnA b (hBnA b hb)]
      exact hbeq

/-- The positive and negative letter-0 pieces in $M$ are disjoint: no point can have
`wrd` starting with both $(0, \mathrm{true})$ and $(0, \mathrm{false})$. -/
theorem letter0_pieces_disjoint (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    Disjoint {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)}
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} := by grind

/-- The letter-0 source set equals the union of the positive and negative letter-0 pieces:
elements of $M$ whose first letter index is $0$ are exactly those whose first letter is
$(0, \mathrm{true})$ or $(0, \mathrm{false})$. -/
theorem letter0_source_eq_union (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}
      = {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)}
        ∪ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} := by aesop

/-- The positive and negative letter-1 pieces in $M$ are disjoint: no point can have
`wrd` starting with both $(1, \mathrm{true})$ and $(1, \mathrm{false})$. -/
theorem b_letter_pieces_disjoint (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    Disjoint {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)}
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)} := by grind

/-- The image of the negative letter-1 piece under the generator-1 action equals $M$ minus
the positive letter-1 piece.

This is the point-set incarnation of the free-group identity
$b \cdot W_b^{-1} = F_2 \setminus W_b$, transported via the equivariance hypothesis `hwrd`. -/
theorem b_letter_split
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x) :
    (fun x => φ (FreeGroup.of 1) • x) ''
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)}
      = M \ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)} := by
  have key : ∀ z ∈ M,
      (FreeGroup.toWord (wrd (φ ((FreeGroup.of 1)⁻¹) • z))).head? = some (1, false)
        ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (1, true) := by
    intro z hz
    rw [hwrd z hz]
    exact head_inv_mul_iff 1 (wrd z)
  ext y
  simp only [Set.mem_image, Set.mem_setOf_eq, Set.mem_diff]
  constructor
  · rintro ⟨x, ⟨hxM, hxhead⟩, rfl⟩
    refine ⟨hinv _ _ hxM, ?_⟩
    rintro ⟨_, hhead⟩
    have hyM : φ (FreeGroup.of 1) • x ∈ M := hinv _ _ hxM
    have hxy : φ ((FreeGroup.of 1)⁻¹) • (φ (FreeGroup.of 1) • x) = x := by
      rw [smul_smul, ← map_mul, inv_mul_cancel, map_one, one_smul]
    have hk := key _ hyM
    rw [hxy] at hk
    exact (hk.mp hxhead) hhead
  · rintro ⟨hyM, hyhead⟩
    refine ⟨φ ((FreeGroup.of 1)⁻¹) • y, ⟨hinv _ _ hyM, ?_⟩, ?_⟩
    · rw [key y hyM]
      intro hc
      exact hyhead ⟨hyM, hc⟩
    · rw [smul_smul, ← map_mul, mul_inv_cancel, map_one, one_smul]

/-- The letter-1 source set equals the set of points in $M$ whose `wrd` value starts with a
letter-1 character.

Points in $M$ that are neither in the letter-0 source nor at the identity word are exactly
those whose first letter is $(1, \mathrm{true})$ or $(1, \mathrm{false})$. -/
theorem letter1_source_eq_diff (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} \
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none}
    = {x | x ∈ M ∧
        ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
         (FreeGroup.toWord (wrd x)).head? = some (1, false))} := by
  ext x
  simp only [Set.mem_diff, Set.mem_setOf_eq]
  constructor
  · rintro ⟨⟨hm, hneq0⟩, hnone⟩
    refine ⟨hm, ?_⟩
    rcases h : (FreeGroup.toWord (wrd x)).head? with _ | ⟨⟨i, b⟩⟩
    · exact absurd ⟨hm, h⟩ hnone
    · have hine : i ≠ 0 := by
        intro hi
        apply hneq0
        simp [h, hi]
      have hi1 : i = 1 := by fin_cases i <;> simp_all
      subst hi1
      cases b
      · right; rfl
      · left; rfl
  · rintro ⟨hm, h | h⟩
    · constructor
      · exact ⟨hm, by simp [h]⟩
      · rintro ⟨-, hn⟩; simp [h] at hn
    · constructor
      · exact ⟨hm, by simp [h]⟩
      · rintro ⟨-, hn⟩; simp [h] at hn

/-- For $z \in M$, the word of $\varphi(a^{-1}) \cdot z$ starts with $(0, \mathrm{false})$
if and only if the word of $z$ does not start with $(0, \mathrm{true})$.

This follows from `hwrd` and `head_inv_mul_iff`. -/
theorem letter0_head_flip
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x)
    (z : E) (hz : z ∈ M) :
    (FreeGroup.toWord (wrd (φ ((FreeGroup.of 0)⁻¹) • z))).head? = some (0, false)
      ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (0, true) := by
  rw [hwrd z hz]; exact head_inv_mul_iff 0 (wrd z)

/-- The image of the negative letter-0 piece under the generator-0 action equals $M$ minus
the positive letter-0 piece.

This is the point-set incarnation of the free-group identity
$a \cdot W_a^{-1} = F_2 \setminus W_a$, transported via the equivariance hypothesis `hwrd`.
The key ingredient is `letter0_head_flip`. -/
theorem letter0_split
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (wrd : E → FreeGroup (Fin 2))
    (hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x) :
    (fun x => φ (FreeGroup.of 0) • x) ''
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)}
      = M \ {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)} := by
  have key : ∀ z ∈ M,
      (FreeGroup.toWord (wrd (φ ((FreeGroup.of 0)⁻¹) • z))).head? = some (0, false)
        ↔ (FreeGroup.toWord (wrd z)).head? ≠ some (0, true) :=
    fun z hz => letter0_head_flip φ M wrd hwrd z hz
  ext y
  simp only [Set.mem_image, Set.mem_setOf_eq, Set.mem_diff]
  constructor
  · rintro ⟨x, ⟨hxM, hxhead⟩, rfl⟩
    refine ⟨hinv _ _ hxM, ?_⟩
    rintro ⟨_, hhead⟩
    have hyM : φ (FreeGroup.of 0) • x ∈ M := hinv _ _ hxM
    have hxy : φ ((FreeGroup.of 0)⁻¹) • (φ (FreeGroup.of 0) • x) = x := by
      rw [smul_smul, ← map_mul, inv_mul_cancel, map_one, one_smul]
    have hk := key _ hyM
    rw [hxy] at hk
    exact (hk.mp hxhead) hhead
  · rintro ⟨hyM, hyhead⟩
    refine ⟨φ ((FreeGroup.of 0)⁻¹) • y, ⟨hinv _ _ hyM, ?_⟩, ?_⟩
    · rw [key y hyM]
      intro hc
      exact hyhead ⟨hyM, hc⟩
    · rw [smul_smul, ← map_mul, mul_inv_cancel, map_one, one_smul]

end Library.Geometry.BanachTarski.SphereDecompPieces
