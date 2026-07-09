import Mathlib
import Problems.Topology.mayer_vietoris.Defs

namespace Problems.Topology.mayer_vietoris

theorem main : True := by sorry

end Problems.Topology.mayer_vietoris

def A : Type := sorry
def f : A → Type := sorry
def g (x : A) : f x := sorry

def B : Type := Σ (x : A), f x
def b (a : A) : B := ⟨a, g a⟩

def C : Type := Π (x : A), f x
def c : C := g

inductive Vect (α : Type u) : Nat → Type u
  | nil  : Vect α 0
  | cons : α → {n : Nat} → Vect α n → Vect α (n + 1)

inductive Vect' (α : Type u) : Nat → Type u
| nil  : Vect' α 0
| cons : α → {n : Nat} → Vect' α n → Vect' α (n + 1)


#check B
