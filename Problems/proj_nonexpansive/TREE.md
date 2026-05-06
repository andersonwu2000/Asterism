# proj_nonexpansive — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved, attempts=1)
└── via s1  (succeeded)
    ├── inner_sq_bound  (proved)
    │   └── via s3  (succeeded)
    │       └── inner_sq_from_two_var_ineq  (proved, attempts=1)
    ├── norm_le_of_inner_sq  (proved)
    └── variational_ineq  (proved, attempts=1)
        └── via s2  (succeeded)
            ├── convex_combo_in_set  (proved)
            └── inner_le_zero_of_norm_le  (proved)
                └── via s4  (succeeded)
                    ├── inner_le_zero_of_t_bound  (proved)
                    │   └── via s6  (succeeded)
                    │       ├── le_zero_of_forall_lin_bound  (proved)
                    │       │   └── via s7  (succeeded)
                    │       │       ├── c_nonpos_from_two_c_le_eps  (proved)
                    │       │       └── forall_pos_two_c_le_eps  (proved)
                    │       │           └── via s8  (succeeded)
                    │       │               └── exists_t_witness  (proved, attempts=1)
                    │       │                   └── via s9  (succeeded)
                    │       │                       ├── t_witness_pos_m  (proved)
                    │       │                       │   └── via s10  (succeeded)
                    │       │                       │       ├── t_witness_pos_m_le_one  (proved)
                    │       │                       │       ├── t_witness_pos_m_mul_le  (proved)
                    │       │                       │       └── t_witness_pos_m_pos  (proved)
                    │       │                       └── t_witness_zero_m  (proved)
                    │       └── lin_bound_from_quad  (proved)
                    └── inner_sq_bound_2  (proved)
                        └── via s5  (succeeded)
                            ├── norm_sq_ineq  (proved)
                            └── norm_sub_smul_sq_expand  (proved)
```

**Counters:** 21 proved
