# LinearAlgebra.normal_diagonalization — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved, attempts=1)
└─ via s11530  (succeeded)
   ├─ block_triangular_basis  (proved)
   │  └─ via s11531  (succeeded)
   │     └─ adapted_orthonormal_basis  (proved, attempts=1)
   │        └─ via s11544  (succeeded)
   │           ├─ flag_invariant  (proved)
   │           │  └─ via s11546  (succeeded)
   │           └─ flag_span_eq  (proved)
   │              └─ via s11547  (succeeded)
   ├─ commute_bridge  (proved)
   │  └─ via s11543  (succeeded)
   └─ matrix_core  (proved)
      └─ via s11534  (succeeded)
         ├─ row_col_norm_eq  (proved)
         └─ triangular_rowcol_eq_imp_diag  (proved, attempts=1)
            └─ via s11545  (succeeded)
               ├─ col_sum_collapse  (proved)
               └─ sum_norm_sq_eq_single_imp_zero  (proved)
```

**Counters:** 11 proved
