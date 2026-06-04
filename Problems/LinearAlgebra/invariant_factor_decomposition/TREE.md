# LinearAlgebra.invariant_factor_decomposition — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└─ via s11563  (succeeded)
   ├─ primary_form  (proved)
   │  └─ via s11564  (succeeded)
   │     └─ monic_directsum_of_torsion  (proved)
   │        └─ via s11566  (succeeded)
   │           └─ exists_monic_quot_equiv  (proved)
   │              └─ via s11567  (succeeded)
   └─ recombine_invariant_factors  (proved, attempts=1)
      ├─ via s11565  (dead)
      └─ via s11571  (succeeded)
         ├─ divchain_column_products  (proved)
         └─ recombine_unified  (proved)
            └─ via s11572  (succeeded)
               ├─ directsum_grid_crt  (proved, attempts=1)
               │  └─ via s11573  (succeeded)
               │     └─ crt_row_collapse  (proved)
               └─ prime_power_regroup  (proved, attempts=1)
                  ├─ via s11574  (dead — sub-goal shelved)
                  │  ├─ directsum_reindex_padded  (shelved, attempts=1)
                  │  │  └─ via s11575  (dead)
                  │  └─ exists_grid_reindex  (dead, attempts=1)
                  │     └─ via s11576  (dead)
                  └─ via s11577  (succeeded)
                     ├─ grid_data  (proved)
                     │  └─ via s11579  (succeeded)
                     │     ├─ distinct_primes  (proved)
                     │     │  └─ via s11580  (succeeded)
                     │     │     ├─ coprime_distinct_monic_irred  (proved)
                     │     │     └─ enum_finite_image  (proved)
                     │     │        └─ via s11584  (succeeded)
                     │     ├─ row_nonunit  (proved)
                     │     └─ sorted_grid  (proved, attempts=1)
                     │        └─ via s11581  (dead)
                     └─ reindex_iso  (proved)
                        └─ via s11578  (succeeded)
                           ├─ assoc_quot_lequiv  (proved)
                           ├─ directsum_prod_uncurry  (proved)
                           │  └─ via s11582  (succeeded)
                           ├─ reindex_drop_subsingleton  (proved, attempts=1)
                           │  └─ via s11583  (succeeded)
                           │     └─ drop_subsingleton_subtype  (proved)
                           │        └─ via s11586  (succeeded)
                           └─ subsingleton_quot_span_one  (proved)
```

## Forward

```
crt_directsum_prod_quot  (proved, attempts=1)
└─ via s11568  (succeeded)
   ├─ crt_quot_inf_pi  (proved)
   │  └─ via s11569  (succeeded)
   └─ inf_span_eq_span_prod  (proved)
      └─ via s11570  (succeeded)

monotone_grid_of_keyed_exponents  (proved, attempts=3)
└─ via s11585  (succeeded)
   ├─ assemble_grid  (proved, attempts=1)
   │  └─ via s11587  (succeeded)
   └─ column_block  (proved, attempts=1)
      └─ via s11588  (succeeded)
         └─ sorted_enum  (proved)
```

**Counters:** 29 proved / 1 shelved
