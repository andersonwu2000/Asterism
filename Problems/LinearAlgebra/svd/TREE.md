# LinearAlgebra.svd — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└─ via s10850  (succeeded)
   ├─ eigenbasis_t_adjoint_t  (proved, attempts=1)
   │  └─ via s10851  (succeeded)
   │     ├─ eigenbasis_apply_eq_sq_singular_values  (proved)
   │     │  └─ via s10853  (succeeded)
   │     └─ t_adjoint_t_is_symmetric  (proved)
   └─ svd_complete_from_eigenbasis  (proved, attempts=1)
      └─ via s10852  (succeeded)
         ├─ exists_b_f_with_matrix_diag  (proved)
         │  └─ via s10854  (succeeded)
         │     ├─ exists_b_f_apply_eq  (proved)
         │     │  └─ via s10855  (succeeded)
         │     │     ├─ b_f_apply_eq_dite  (proved)
         │     │     │  └─ via s10856  (succeeded)
         │     │     │     ├─ exists_b_f_apply_eq_dite_with_zero  (proved)
         │     │     │     │  └─ via s10858  (succeeded)
         │     │     │     │     ├─ exists_b_f_apply_eq_nonzero  (proved)
         │     │     │     │     │  └─ via s10859  (succeeded)
         │     │     │     │     │     └─ normalized_t_orthonormal_on_supp  (proved)
         │     │     │     │     └─ t_b_e_zero_of_sigma_zero  (proved)
         │     │     │     └─ t_apply_eigenbasis_zero_high  (proved)
         │     │     │        └─ via s10857  (succeeded)
         │     │     │           ├─ singular_values_zero_high  (proved)
         │     │     │           └─ t_apply_zero_of_singular_zero  (proved)
         │     │     └─ sum_ite_smul_eq_dite  (proved)
         │     └─ matrix_eq_of_apply_eq  (proved)
         └─ inner_t_eigenbasis_sq_diag  (proved)
```

**Counters:** 18 proved
