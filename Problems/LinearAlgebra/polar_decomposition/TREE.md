# LinearAlgebra.polar_decomposition — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└─ via s11548  (succeeded)
   ├─ p_is_positive  (proved, attempts=1)
   │  └─ via s11550  (succeeded)
   │     ├─ p_inner_nonneg  (proved, attempts=1)
   │     │  └─ via s11551  (succeeded)
   │     │     ├─ p_inner_re_eq_sum  (proved)
   │     │     │  └─ via s11553  (succeeded)
   │     │     │     ├─ inner_diag_sum_eq_weighted  (proved)
   │     │     │     ├─ p_constr_apply_eq_sum  (proved)
   │     │     │     └─ re_sum_weighted_eq_real_sum  (proved)
   │     │     └─ p_sum_sigma_norm_nonneg  (proved)
   │     └─ p_symmetric  (proved)
   │        └─ via s11552  (succeeded)
   │           └─ p_matrix_hermitian  (proved)
   ├─ t_factorization  (proved)
   │  └─ via s11549  (succeeded)
   └─ u_isometry  (proved)
```

**Counters:** 12 proved
