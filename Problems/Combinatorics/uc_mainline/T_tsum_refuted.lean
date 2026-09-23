import Mathlib
import Problems.Combinatorics.uc_mainline.Defs

/-!
# Theorem 10.22 of `uc_global_counting.md` (`T_sum` is false; the family `W(t)`)

> **Theorem 10.22 (`T_sum` is false; the family `W(t)`).** Fix `t ≥ 1`, let
> `V = {b, c, d} ∪ T` with `|T| = t` and `T` disjoint from `{b, c, d}`, let `x`
> be a further coordinate, and put
>
>     A = { ∅, {b}, V ∖ {d}, V },        B = { {d}, {b,d}, {b,c,d}, V }.
>
> Then `W(t) := A ∪ (B + x)` is union-closed with `∅`, `x` is tight, `N = 8`,
> `s = N/2 = 4`, `(A_x, B_x) = (A, B)`, `h(x) = 1`, and
>
>     sp_F(b) = 4,  sp_F(c) = 0,  sp_F(d) = 2,  sp_F(τ) = −2 (τ ∈ T),
>     Σ_{a ∈ A_x} sp_F(a) = 14 − 4t.
>
> For `t ≥ 4` the row sum is negative while `h(x) = 1`, so `T_sum` fails at the
> *minimal* Hall violation; `t = 4` gives a family with `n = 8` coordinates and
> `N = 8` rows.

(`uc_global_counting.md`, Section 10; `T_sum : h(x) > 0 ⟹ Σ_{a ∈ A_x} sp_F(a) > 0`.)
Formalised at the explicit `t = 4` on `Fin 8`, with `x = 0`, `b = 1`, `c = 2`,
`d = 3`, `T = {4, 5, 6, 7}`, so the article's `V` is `{1, …, 7}`.
`h(x) = hallDef`, `sp_F = surplus`, `sp_F(a) = rowSurplus`.
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

-- The two theorems below are pure `Fin 8` computations; give the kernel room.
set_option maxRecDepth 100000
set_option maxHeartbeats 2000000

/-- The article's ground `V = {b, c, d} ∪ T` at `t = 4`: all coordinates but `x = 0`. -/
def wV : Finset (Fin 8) := {1, 2, 3, 4, 5, 6, 7}

/-- `A = { ∅, {b}, V ∖ {d}, V }`. -/
def wA : Finset (Finset (Fin 8)) := {∅, {1}, {1, 2, 4, 5, 6, 7}, wV}

/-- `B = { {d}, {b,d}, {b,c,d}, V }`. -/
def wB : Finset (Finset (Fin 8)) := {{3}, {1, 3}, {1, 2, 3}, wV}

/-- `W(4) = A ∪ (B + x)`. -/
def wFamily : Finset (Finset (Fin 8)) := wA ∪ wB.image (fun S => insert 0 S)

/-- Theorem 10.22 at `t = 4`: `W(4)` is union-closed with `∅`, `x` is tight,
`N = 8`, `(A_x, B_x) = (A, B)`, `h(x) = 1`, the four surplus values, and
`Σ_{a ∈ A_x} sp_F(a) = 14 − 4·4 = −2`. -/
theorem tsum_refuted_t4 :
    UnionClosed wFamily ∧ ∅ ∈ wFamily ∧ Tight wFamily 0 ∧ wFamily.card = 8 ∧
    zeroSlice wFamily 0 = wA ∧ oneSlice wFamily 0 = wB ∧ hallDef wFamily 0 = 1 ∧
    surplus wFamily 1 = 4 ∧ surplus wFamily 2 = 0 ∧ surplus wFamily 3 = 2 ∧
    (∀ τ ∈ ({4, 5, 6, 7} : Finset (Fin 8)), surplus wFamily τ = -2) ∧
    ∑ a ∈ zeroSlice wFamily 0, rowSurplus wFamily a = 14 - 4 * 4 := by
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩ <;> decide +kernel

/-- Theorem 10.22, the refutation clause: at `t = 4` the Hall deficiency is
positive while the row sum of the zero slice is negative, so `T_sum` fails. -/
theorem tsum_fails_t4 :
    0 < hallDef wFamily 0 ∧ ∑ a ∈ zeroSlice wFamily 0, rowSurplus wFamily a < 0 := by
  refine ⟨?_, ?_⟩ <;> decide +kernel

#print axioms tsum_refuted_t4
#print axioms tsum_fails_t4

end Problems.Combinatorics.uc_mainline
