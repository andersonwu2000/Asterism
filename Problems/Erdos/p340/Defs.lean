import Mathlib

set_option maxHeartbeats 400000

open Filter Finset
open scoped Real Pointwise

namespace Problems.Erdos.p340

/- The charter's statement is written in `greedySidon`, which lives in
formal-conjectures' shared library, not in the per-problem source file —
the import adapter carried the statement and dropped its vocabulary
(caught 2026-08-22, the only such problem of the 46). Ported verbatim
from google-deepmind/formal-conjectures
`FormalConjecturesForMathlib/Combinatorics/Basic.lean` (Apache-2.0);
vocabulary only, no results about it. -/

/-- A Sidon set is a set such that all pairwise sums of elements are
distinct apart from coincidences forced by the commutativity of
addition. -/
def IsSidon {α : Type*} [AddCommMonoid α] (A : Set α) : Prop :=
  ∀ᵉ (i₁ ∈ A) (j₁ ∈ A) (i₂ ∈ A) (j₂ ∈ A),
    i₁ + i₂ = j₁ + j₂ → (i₁ = j₁ ∧ i₂ = j₂) ∨ (i₁ = j₂ ∧ i₂ = j₁)

theorem IsSidon.insert {α : Type*} [AddCommMonoid α] {A : Set α} {m : α}
    [IsRightCancelAdd α] [IsLeftCancelAdd α] (hA : IsSidon A) :
    IsSidon (A ∪ {m}) ↔ (m ∈ A ∨ ∀ᵉ (a ∈ A) (b ∈ A), m + m ≠ a + b ∧ ∀ c ∈ A, m + a ≠ b + c) := by
  by_cases h_mem : m ∈ A
  · exact ⟨fun _ ↦ .inl h_mem, fun _ ↦ by
      rwa [Set.union_singleton, Set.insert_eq_of_mem h_mem]⟩
  refine ⟨fun h ↦ .inr fun a ha b hb ↦ ⟨fun hc ↦ ?_, fun c hc h_contr ↦ ?_⟩, fun hm ↦ ?_⟩
  · exact h m (by simp) a (by simp [ha]) m (by simp) b (by simp [hb]) hc
      |>.elim (fun _ ↦ by simp_all) (fun _ ↦ by simp_all)
  · exact h m (by simp) b (by simp [hb]) a (by simp [ha]) c (by simp [hc]) h_contr
      |>.elim (fun _ ↦ by simp_all) (fun _ ↦ by simp_all)
  · intro i₁ hi₁
    rcases hi₁ with (hi₁ | hi₁)
    · intro j₁ hj₁
      rcases hj₁ with (hj₁ | hj₁)
      · intro i₂ hi₂
        rcases hi₂ with (hi₂ | hi₂)
        · intro j₂ hj₂
          rcases hj₂ with (hj₂ | hj₂)
          · exact fun h ↦ hA i₁ hi₁ j₁ hj₁ i₂ hi₂ j₂ hj₂ h
          · simp_all
            exact fun h ↦ by cases (hm j₁ hj₁ i₁ hi₁).2 i₂ hi₂ (add_comm j₁ m ▸ h.symm)
        · simp_all
          exact fun a ha h ↦ by cases (hm i₁ hi₁ j₁ hj₁).2 a ha (add_comm i₁ m ▸ h)
      · simp_all
        refine ⟨fun b hb h ↦ .inr <| by simp_all [add_comm], fun b hb ↦ ⟨fun h ↦ ?_, ?_⟩⟩
        · cases (hm i₁ hi₁ b hb).1 h.symm
        · exact fun c hc h ↦ by cases ((hm c hc i₁ hi₁).2 b hb) h.symm
    · simp_all
      exact fun _ _ _ _ _ ↦ by simp_all [add_comm]

instance {α : Type*} [AddCommMonoid α] (A : Finset α) [DecidableEq α] :
    Decidable (IsSidon (A : Set α)) := by
  refine decidable_of_iff (∀ᵉ (i₁ ∈ A) (j₁ ∈ A) (i₂ ∈ A) (j₂ ∈ A),
    i₁ + i₂ = j₁ + j₂ → (i₁ = j₁ ∧ i₂ = j₂) ∨ (i₁ = j₂ ∧ i₂ = j₁)) ?_
  rfl

/-- If `A` is finite Sidon, then `A ∪ {s}` is also Sidon provided
`s ≥ 2 * A.max + 1`. -/
theorem IsSidon.insert_ge_max' {A : Finset ℕ} (h : A.Nonempty)
    (hA : IsSidon (A : Set ℕ)) {s : ℕ} (hs : 2 * A.max' h + 1 ≤ s) :
    IsSidon (↑(A ∪ {s}) : Set ℕ) := by
  have hsA : s ∉ A := by
    exact mt (A.le_max' _) <| not_le.2 <| Finset.max'_lt_iff _ ‹_› |>.2 fun a ha ↦ by
      linarith [A.le_max' _ ha]
  rw [Finset.coe_union, Finset.coe_singleton]
  refine (IsSidon.insert (m := s) hA).2 (Or.inr fun a ha b hb ↦ ?_)
  have ha' : a ∈ A := ha
  have hb' : b ∈ A := hb
  refine ⟨fun hc ↦ ?_, fun c hc hcontr ↦ ?_⟩
  · linarith [A.le_max' _ ha', A.le_max' _ hb']
  · have hc' : c ∈ A := hc
    linarith [A.le_max' _ hb', A.le_max' _ hc']

theorem IsSidon.exists_insert_ge {A : Finset ℕ} (h : A.Nonempty)
    (hA : IsSidon (A : Set ℕ)) (s : ℕ) :
    ∃ m ≥ s, m ∉ A ∧ IsSidon (↑(A ∪ {m}) : Set ℕ) := by
  refine ⟨if s ≥ 2 * A.max' h + 1 then s else 2 * A.max' h + 1, ?_, ?_, ?_⟩
  · split_ifs <;> linarith
  · split_ifs <;>
    exact mt (A.le_max' _) <| not_le.2 <| Finset.max'_lt_iff _ ‹_› |>.2 fun a ha ↦ by
      linarith [A.le_max' _ ha]
  · split_ifs with hs
    · exact insert_ge_max' h hA hs
    · exact insert_ge_max' h hA le_rfl

/-- Given a finite Sidon set `A` and a lower bound `m`, `go` finds the
smallest number `m' ≥ m` such that `A ∪ {m'}` is Sidon. If `A` is empty
then this returns the value `m`. -/
def greedySidon.go (A : Finset ℕ) (hA : IsSidon (A : Set ℕ)) (m : ℕ) :
    {m' : ℕ // m' ≥ m ∧ m' ∉ A ∧ IsSidon (↑(A ∪ {m'}) : Set ℕ)} :=
  if h : A.Nonempty then
    have : ∃ m', m' ≥ m ∧ m' ∉ A ∧ IsSidon (↑(A ∪ {m'}) : Set ℕ) := by
      simpa [and_assoc] using IsSidon.exists_insert_ge h hA m
    ⟨Nat.find this, Nat.find_spec this⟩
  else ⟨m, by simp_all [IsSidon]⟩

/-- Main search loop for generating the greedy Sidon sequence. -/
def greedySidon.aux (n : ℕ) : ({A : Finset ℕ // IsSidon (A : Set ℕ)} × ℕ) :=
  match n with
  | 0 => (⟨{1}, by simp [IsSidon]⟩, 1)
  | k + 1 =>
    let (A, s) := greedySidon.aux k
    let s := if h : A.1.Nonempty then A.1.max' h + 1 else s
    let s' := greedySidon.go A.1 A.2 s
    (⟨A.1 ∪ {s'.1}, s'.2.2.2⟩, s'.1)

/-- `greedySidon` is the sequence obtained by the initial set $\{1\}$ and
iteratively obtaining the next smallest integer that preserves the Sidon
property of the set. This gives the sequence `1, 2, 4, 8, 13, 21, 31, …`. -/
def greedySidon (n : ℕ) : ℕ := greedySidon.aux n |>.2

end Problems.Erdos.p340
