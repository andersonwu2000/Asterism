/-
  Sandbox disproof of the minif2f-transcribed statement of `amc12a_2002_p21`.

  ## Background
  The original AMC 2002 12A #21 defines a sequence by u 0 = 4, u 1 = 7, and
  the recurrence  u (n+2) = (u n + u (n+1)) % 10  for ALL n ≥ 0. The
  miniF2F Lean transcription accidentally restricts the recurrence to
  n ≥ 2, leaving u 2 and u 3 entirely unconstrained.

  ## What we prove here
  The miniF2F-transcribed statement is FALSE. We exhibit u with
  u 0=4, u 1=7, u 2=10000, u 3=0, u k=0 for k≥4. It satisfies h₀, h₁,
  h₂ as written but ∑_{k<3} u k = 10011 > 10000 while 3 < 1999.

  ## How to verify
    cd D:/Asterism
    lake env lean .asterism/sandbox/amc12a_2002_p21_disproof.lean
  Expected: clean elaboration (only the file's own `theorem disproof :=`
  using axioms `[propext, Classical.choice, Quot.sound]` — no sorryAx).
-/
import Mathlib

namespace Minif2fErrata.Amc12a2002P21

/-- Counterexample sequence: 4, 7, 10000, 0, 0, 0, ... -/
def cex_u : ℕ → ℕ
  | 0 => 4
  | 1 => 7
  | 2 => 10000
  | _ => 0

/-- The miniF2F statement, written exactly as imported via our adapter. -/
def stmt : Prop :=
  ∀ (u : ℕ → ℕ) (_ : u 0 = 4) (_ : u 1 = 7)
    (_ : ∀ n ≥ 2, u (n + 2) = (u n + u (n + 1)) % 10),
    ∀ n, (∑ k ∈ Finset.range n, u k) > 10000 → 1999 ≤ n

theorem disproof : ¬ stmt := by
  intro h
  -- Verify h₀, h₁ by rfl (cex_u 0 = 4, cex_u 1 = 7 by definition)
  have h0 : cex_u 0 = 4 := rfl
  have h1 : cex_u 1 = 7 := rfl
  -- Verify h₂: for n ≥ 2, cex_u (n+2) = (cex_u n + cex_u (n+1)) % 10
  have h2 : ∀ n ≥ 2, cex_u (n + 2) = (cex_u n + cex_u (n + 1)) % 10 := by
    intro n hn
    match n, hn with
    -- n=2: cex_u 4 = 0;  (cex_u 2 + cex_u 3) % 10 = (10000+0)%10 = 0
    | 2, _ => rfl
    -- n=3: cex_u 5 = 0;  (cex_u 3 + cex_u 4) % 10 = (0+0)%10 = 0
    | 3, _ => rfl
    -- n ≥ 4: cex_u (n+2) = 0 and cex_u n = cex_u (n+1) = 0
    | (m + 4), _ => rfl
  -- Apply hypothesis at n = 3
  have step := h cex_u h0 h1 h2 3
  -- Premise of step: ∑ k ∈ range 3, cex_u k > 10000
  --   = cex_u 0 + cex_u 1 + cex_u 2 = 4 + 7 + 10000 = 10011
  have hsum : (∑ k ∈ Finset.range 3, cex_u k) > 10000 := by
    show (∑ k ∈ Finset.range 3, cex_u k) > 10000
    rw [Finset.sum_range_succ, Finset.sum_range_succ, Finset.sum_range_succ,
        Finset.sum_range_zero]
    decide
  -- Apply implication, get 1999 ≤ 3, which is false.
  exact absurd (step hsum) (by decide)

end Minif2fErrata.Amc12a2002P21

#print axioms Minif2fErrata.Amc12a2002P21.disproof
