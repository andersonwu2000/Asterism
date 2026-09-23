import Mathlib

/-!
# Vocabulary of the union-closed main line

Formal counterpart of the vocabulary used in the research articles
`uc_minimal_deficit_pair.md` (Sections 1, 5b, 5b.3), `uc_tight_coordinate.md`
(Sections 1, 8, 10), `uc_excess_transport.md` (Section 1) and
`uc_global_counting.md` (Section 10).

The ground set is a finite type `V` with decidable equality; a *family* is a
`Finset (Finset V)`.  Every definition is computable so that small cases can be
settled by `decide`.

Dictionary (article notation on the left):

* `F` union-closed with `∅`                 — `UnionClosed F`, `∅ ∈ F`
* `N = |F|`                                 — `F.card`
* `d_F(j)`                                  — `deg F j`
* `sp_F(j) = 2 d_F(j) − N`                  — `surplus F j`  (`ℤ`)
* `σ_j(F) = N − 2 d_F(j)`                   — `sigma F j`    (`ℤ`)
* `j` active                                — `Active F j`
* capped / regular / tight / rare / abundant — `Capped`, `Regular`, `Tight`, `Rare`, `Abundant`
* `π_x(F) = {S ∖ {x} : S ∈ F}`              — `proj F x`
* `A_x = {S ∈ F : x ∉ S}`                   — `zeroSlice F x`
* `B_x = {S ∖ {x} : x ∈ S ∈ F}`             — `oneSlice F x`
* `I_x = C_x = A_x ∩ B_x`                   — `edgeTrace F x`
* `U_x = ∪ A_x`                             — `zeroGround F x`
* `k ⇒ x`                                   — `Implies F k x`
* pattern class `F[P, p]`                   — `patternClass F P p`
* `X, Y, Z, W` at `(x, k)`                  — `patX`, `patY`, `patZ`, `patW`
* `π_{x,k}(F)`                              — `pairProj F x k`
* `D(x → k)`                                — `witnessD F x k`
* `τ(F) = min{|a| : ∅ ≠ a ∈ F}`             — `tau F`
* type `m(b)`, `μ`, Hall deficiency `e* = h(x)` — `rowType`, `mu`, `hallDef`
* downward bijection / common fold `H = A_x` — `IsFold F x`
* section `Q'` and its endpoint `F_{Q'}`    — `LegalSection`, `sectionEndpoint`
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

variable {V : Type*} [DecidableEq V] [Fintype V]

/-! ## Basic family vocabulary -/

/-- `F` is union-closed: the union of two members is a member. -/
def UnionClosed (F : Finset (Finset V)) : Prop :=
  ∀ a ∈ F, ∀ b ∈ F, a ∪ b ∈ F

instance (F : Finset (Finset V)) : Decidable (UnionClosed F) :=
  inferInstanceAs (Decidable (∀ a ∈ F, ∀ b ∈ F, a ∪ b ∈ F))

/-- The degree `d_F(j)`: the number of members of `F` containing `j`. -/
def deg (F : Finset (Finset V)) (j : V) : ℕ :=
  (F.filter (fun S => j ∈ S)).card

/-- The surplus `sp_F(j) = 2 d_F(j) − N` (tight-coordinate article, Section 1). -/
def surplus (F : Finset (Finset V)) (j : V) : ℤ :=
  2 * (deg F j : ℤ) - (F.card : ℤ)

/-- The deficit `σ_j(F) = N − 2 d_F(j)` (pair article, Sections 1 and 5b). -/
def sigma (F : Finset (Finset V)) (j : V) : ℤ :=
  (F.card : ℤ) - 2 * (deg F j : ℤ)

/-- `j` is active in `F`: some member contains it. -/
def Active (F : Finset (Finset V)) (j : V) : Prop := 0 < deg F j

instance (F : Finset (Finset V)) (j : V) : Decidable (Active F j) :=
  inferInstanceAs (Decidable (0 < deg F j))

/-- The active ground of `F`. -/
def ground (F : Finset (Finset V)) : Finset V :=
  univ.filter (fun j => Active F j)

/-- Capped: `σ_j(F) ≥ 0`, i.e. `2 d_F(j) ≤ N`, at every coordinate.  (An inactive
coordinate has `σ_j = N ≥ 0`, so quantifying over all of `V` agrees with the
articles' "every coordinate of the active ground".) -/
def Capped (F : Finset (Finset V)) : Prop := ∀ j : V, 0 ≤ sigma F j

instance (F : Finset (Finset V)) : Decidable (Capped F) :=
  inferInstanceAs (Decidable (∀ j : V, 0 ≤ sigma F j))

/-- Regular: every active coordinate is tight (`σ_j(F) = 0`). -/
def Regular (F : Finset (Finset V)) : Prop := ∀ j : V, Active F j → sigma F j = 0

instance (F : Finset (Finset V)) : Decidable (Regular F) :=
  inferInstanceAs (Decidable (∀ j : V, Active F j → sigma F j = 0))

/-- Tight coordinate: `σ_j(F) = 0`. -/
def Tight (F : Finset (Finset V)) (j : V) : Prop := sigma F j = 0

instance (F : Finset (Finset V)) (j : V) : Decidable (Tight F j) :=
  inferInstanceAs (Decidable (sigma F j = 0))

/-- Rare coordinate: `σ_j(F) > 0`. -/
def Rare (F : Finset (Finset V)) (j : V) : Prop := 0 < sigma F j

instance (F : Finset (Finset V)) (j : V) : Decidable (Rare F j) :=
  inferInstanceAs (Decidable (0 < sigma F j))

/-- Abundant coordinate: `σ_j(F) < 0` (over the cap). -/
def Abundant (F : Finset (Finset V)) (j : V) : Prop := sigma F j < 0

instance (F : Finset (Finset V)) (j : V) : Decidable (Abundant F j) :=
  inferInstanceAs (Decidable (sigma F j < 0))

/-- No clones (separation): two coordinates lying in the same rows are equal. -/
def Separating (F : Finset (Finset V)) : Prop :=
  ∀ j k : V, (∀ S ∈ F, (j ∈ S ↔ k ∈ S)) → j = k

/-- `k ⇒ x`: every row containing `k` contains `x`. -/
def Implies (F : Finset (Finset V)) (k x : V) : Prop :=
  ∀ S ∈ F, k ∈ S → x ∈ S

instance (F : Finset (Finset V)) (k x : V) : Decidable (Implies F k x) :=
  inferInstanceAs (Decidable (∀ S ∈ F, k ∈ S → x ∈ S))

/-- Shortest-row length `τ(F) = min{|a| : ∅ ≠ a ∈ F}` (`⊤` when `F ⊆ {∅}`). -/
def tau (F : Finset (Finset V)) : WithTop ℕ :=
  ((F.filter (fun a => a ≠ ∅)).image Finset.card).min

/-- The row surplus `sp_F(a) = Σ_{j ∈ a} sp_F(j)` (global counting, Section 10). -/
def rowSurplus (F : Finset (Finset V)) (a : Finset V) : ℤ :=
  ∑ j ∈ a, surplus F j

/-! ## `|V|`-minimality (Frame D) -/

/-- `|V|`-minimality in the class of capped nonregular union-closed families
with `∅`: no such family on the same type has a strictly smaller active
ground.  (Any family on fewer coordinates embeds into `V`, so this is the
articles' `|V|`-minimality.) -/
def Minimal (F : Finset (Finset V)) : Prop :=
  ∀ G : Finset (Finset V), UnionClosed G → ∅ ∈ G → Capped G → ¬ Regular G →
    (ground F).card ≤ (ground G).card

/-- Frame D: union-closed with `∅`, every coordinate active, capped, nonregular,
and `|V|`-minimal among such families. -/
def FrameD (F : Finset (Finset V)) : Prop :=
  UnionClosed F ∧ ∅ ∈ F ∧ (∀ j : V, Active F j) ∧ Capped F ∧ ¬ Regular F ∧ Minimal F

/-! ## One coordinate: slices, projection, edge traces -/

/-- The projection `π_x(F) = {S ∖ {x} : S ∈ F}`. -/
def proj (F : Finset (Finset V)) (x : V) : Finset (Finset V) :=
  F.image (fun S => S.erase x)

/-- The zero slice `A_x = {S ∈ F : x ∉ S}`. -/
def zeroSlice (F : Finset (Finset V)) (x : V) : Finset (Finset V) :=
  F.filter (fun S => x ∉ S)

/-- The one slice `B_x = {S ∖ {x} : x ∈ S ∈ F}` (traces of the `x`-rows). -/
def oneSlice (F : Finset (Finset V)) (x : V) : Finset (Finset V) :=
  (F.filter (fun S => x ∈ S)).image (fun S => S.erase x)

/-- The `x`-edge traces `I_x = C_x = {c : c ∈ F, x ∉ c, c ∪ {x} ∈ F}`
(pair article, Section 5b: `C_x = A_x ∩ B_x`). -/
def edgeTrace (F : Finset (Finset V)) (x : V) : Finset (Finset V) :=
  F.filter (fun c => x ∉ c ∧ insert x c ∈ F)

/-- `U_x = ∪ A_x`, the ground of the zero slice. -/
def zeroGround (F : Finset (Finset V)) (x : V) : Finset V :=
  (zeroSlice F x).biUnion id

/-! ## Two coordinates: pattern classes and the pair projection -/

/-- The pattern class `F[P, p] = {S ∖ P : S ∈ F, S ∩ P = p}` (tight-coordinate
article, Section 8, Definition before Lemma 8.26). -/
def patternClass (F : Finset (Finset V)) (P p : Finset V) : Finset (Finset V) :=
  (F.filter (fun S => S ∩ P = p)).image (fun S => S \ P)

/-- `X`: traces of the rows avoiding both `x` and `k`. -/
def patX (F : Finset (Finset V)) (x k : V) : Finset (Finset V) :=
  patternClass F {x, k} ∅

/-- `Y`: traces of the rows containing `x` and avoiding `k`. -/
def patY (F : Finset (Finset V)) (x k : V) : Finset (Finset V) :=
  patternClass F {x, k} {x}

/-- `Z`: traces of the rows containing `k` and avoiding `x`. -/
def patZ (F : Finset (Finset V)) (x k : V) : Finset (Finset V) :=
  patternClass F {x, k} {k}

/-- `W`: traces of the rows containing both `x` and `k`. -/
def patW (F : Finset (Finset V)) (x k : V) : Finset (Finset V) :=
  patternClass F {x, k} {x, k}

/-- The pair projection `π_{x,k}(F) = {S ∖ {x, k} : S ∈ F}` (`G_2` of Section 5b.3). -/
def pairProj (F : Finset (Finset V)) (x k : V) : Finset (Finset V) :=
  F.image (fun S => S \ {x, k})

/-- The witness number `D(x → k) = |X ∩ Y| − |Z ∩ W| − σ_k(F)` of Lemma 2.3 (7)
of the pair article, written on the pattern classes at `(x, k)`. -/
def witnessD (F : Finset (Finset V)) (x k : V) : ℤ :=
  ((patX F x k ∩ patY F x k).card : ℤ) - ((patZ F x k ∩ patW F x k).card : ℤ) - sigma F k

/-! ## The fold vocabulary at a tight source (excess transport, Section 1) -/

/-- The type `m(b) = ∪ {a ∈ A_x : a ⊆ b}` of a row `b` of `B_x`. -/
def rowType (F : Finset (Finset V)) (x : V) (b : Finset V) : Finset V :=
  ((zeroSlice F x).filter (fun a => a ⊆ b)).biUnion id

/-- `D ⊆ A_x` is down-closed in `A_x`. -/
def DownClosedIn (A D : Finset (Finset V)) : Prop :=
  D ⊆ A ∧ ∀ a ∈ A, ∀ d ∈ D, a ⊆ d → a ∈ D

instance (A D : Finset (Finset V)) : Decidable (DownClosedIn A D) :=
  inferInstanceAs (Decidable (D ⊆ A ∧ ∀ a ∈ A, ∀ d ∈ D, a ⊆ d → a ∈ D))

/-- `μ(D) = #{b ∈ B_x : m(b) ∈ D}`. -/
def mu (F : Finset (Finset V)) (x : V) (D : Finset (Finset V)) : ℕ :=
  ((oneSlice F x).filter (fun b => rowType F x b ∈ D)).card

/-- The Hall deficiency `e* = h(x) = max {μ(D) − |D| : D ⊆ A_x down-closed}`
(`D = ∅` gives `0`, so the natural-number maximum is the article's `e*`). -/
def hallDef (F : Finset (Finset V)) (x : V) : ℕ :=
  ((zeroSlice F x).powerset.filter (fun D => DownClosedIn (zeroSlice F x) D)).sup
    (fun D => mu F x D - D.card)

/-- `H = A_x` is a common fold at `x`: a downward bijection `β : B_x → A_x`,
`β(b) ⊆ b` (tight-coordinate article, 7.2 / Section 8). -/
def IsFold (F : Finset (Finset V)) (x : V) : Prop :=
  ∃ β : Finset V → Finset V,
    Set.BijOn β (↑(oneSlice F x)) (↑(zeroSlice F x)) ∧ ∀ b ∈ oneSlice F x, β b ⊆ b

/-! ## Rooted sections at a source (tight-coordinate article, Section 10;
catalogue, Section 4) -/

/-- `J = A ∪ B` at the source `i`. -/
def sliceUnion (F : Finset (Finset V)) (i : V) : Finset (Finset V) :=
  zeroSlice F i ∪ oneSlice F i

/-- A legal section `Q' ⊆ J ∖ C`: lower in `J`, `C ∨ Q' ⊆ C`, and
`Q' ∨ Q' ⊆ Q' ∪ C`. -/
def LegalSection (F : Finset (Finset V)) (i : V) (Q' : Finset (Finset V)) : Prop :=
  Q' ⊆ sliceUnion F i \ edgeTrace F i ∧
  (∀ S ∈ sliceUnion F i, ∀ q ∈ Q', S ⊆ q → S ∈ Q') ∧
  (∀ c ∈ edgeTrace F i, ∀ q ∈ Q', c ∪ q ∈ edgeTrace F i) ∧
  (∀ q ∈ Q', ∀ q' ∈ Q', q ∪ q' ∈ Q' ∪ edgeTrace F i)

/-- The endpoint `F_{Q'} = (C ∪ Q') ∪ ((J ∖ Q') + i)`. -/
def sectionEndpoint (F : Finset (Finset V)) (i : V) (Q' : Finset (Finset V)) :
    Finset (Finset V) :=
  (edgeTrace F i ∪ Q') ∪ (sliceUnion F i \ Q').image (fun S => insert i S)

end Problems.Combinatorics.uc_mainline
