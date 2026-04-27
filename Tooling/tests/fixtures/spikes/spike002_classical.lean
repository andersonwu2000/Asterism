import Mathlib

-- spike-002 part 2: test lemmas likely to use Quot.sound / Classical.choice

-- Quotient / equivalence class operations
#print axioms Finset.sum_comm
#print axioms Multiset.card_add

-- Classical logic / choice
#print axioms Classical.em
#print axioms Classical.choice
#print axioms Classical.indefiniteDescription

-- Real numbers (likely use all three axioms)
#print axioms Real.add_comm
#print axioms Real.sqrt_sq

-- Exists / choice related
#print axioms Nat.find_spec
