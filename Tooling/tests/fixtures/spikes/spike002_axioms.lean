import Mathlib

-- spike-002: Audit axioms of common Mathlib lemmas
-- Question: do they only depend on propext / Quot.sound / Classical.choice?

-- Nat lemmas
#print axioms Nat.add_zero
#print axioms Nat.zero_add
#print axioms Nat.add_comm
#print axioms Nat.add_assoc
#print axioms Nat.mul_comm
#print axioms Nat.mul_assoc
#print axioms Nat.succ_ne_zero
#print axioms Nat.le_refl

-- List lemmas
#print axioms List.length_append
#print axioms List.append_assoc
#print axioms List.map_append

-- Real/Int lemmas (likely use Classical.choice)
#print axioms Int.add_comm
#print axioms Int.mul_comm

-- simp lemmas that Builder will use
#print axioms Nat.add_zero  -- canonical example
