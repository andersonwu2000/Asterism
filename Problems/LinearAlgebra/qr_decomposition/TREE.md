# LinearAlgebra.qr_decomposition — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└─ via s10881  (succeeded)
   └─ orthogonal_upper_triangularizer  (proved, attempts=1)
      └─ via s10882  (succeeded)
         ├─ columns_lin_indep_of_det_ne_zero  (proved)
         └─ orthogonal_upper_triangularizer_of_lin_indep_columns  (proved)
            └─ via s10883  (succeeded)
               ├─ block_triangular_qt_mul_of_span  (proved)
               │  └─ via s10884  (succeeded)
               │     ├─ orthonormal_inner_span_iic_zero  (proved)
               │     └─ qt_mul_entry_eq_inner  (proved)
               ├─ gram_schmidt_ortho_triangular_span  (proved)
               │  └─ via s10885  (succeeded)
               │     ├─ exists_orthonormal_triangular_span_of_li  (proved)
               │     │  └─ via s10886  (succeeded)
               │     └─ li_columns_in_euclidean_space  (proved)
               └─ matrix_of_orthonormal_cols_orthogonal  (proved)
```

**Counters:** 11 proved
