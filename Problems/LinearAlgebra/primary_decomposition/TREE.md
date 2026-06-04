# LinearAlgebra.primary_decomposition — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
```

## Forward

```
exists_finpow_factorization  (proved)
└─ via s11554  (succeeded)
   ├─ finset_factorization  (proved)
   │  └─ via s11557  (succeeded)
   │     ├─ nf_mem_count_pos  (proved)
   │     ├─ nf_mem_irreducible  (proved)
   │     ├─ nf_mem_monic  (proved)
   │     ├─ nf_mem_pairwise_coprime  (proved)
   │     └─ nf_prod_pow_count  (proved)
   │        └─ via s11562  (succeeded)
   └─ fin_of_finset  (proved)
      └─ via s11556  (succeeded)

is_internal_ker_aeval_of_pairwise_coprime  (proved, attempts=1)
└─ via s11555  (succeeded)
   ├─ isup_ker_aeval_eq_ker_aeval_prod  (proved)
   │  └─ via s11558  (succeeded)
   │     ├─ isup_ker_aeval_le_ker_aeval_prod  (proved)
   │     │  └─ via s11561  (succeeded)
   │     │     └─ ker_aeval_le_of_dvd  (proved)
   │     └─ ker_aeval_prod_le_isup_ker_aeval  (proved)
   │        └─ via s11560  (succeeded)
   └─ ker_aeval_isupindep_of_pairwise_coprime  (proved)
      └─ via s11559  (succeeded)
         ├─ coprime_q_prod_erase  (proved)
         └─ sup_ker_le_ker_prod  (proved)
```

**Counters:** 17 proved
