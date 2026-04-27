import Mathlib
-- spike-003: more error cases

-- Case: wrong type annotation (type mismatch)
def bad_type : Nat := "hello"
