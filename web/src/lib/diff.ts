/*
 * Minimal line diff for the amend side-by-side view (dependency freeze:
 * no diff package). LCS over lines, then aligned two-column rows;
 * delete+insert runs are paired into 'change' rows. Amend targets are
 * Manifest.md / Defs.lean — small files, O(n·m) DP is fine (guarded).
 */

export interface DiffRow {
  left: string | null
  right: string | null
  type: 'same' | 'del' | 'add' | 'change'
  leftNo: number | null
  rightNo: number | null
}

export function lineDiff(a: string, b: string): DiffRow[] {
  const al = a.split('\n')
  const bl = b.split('\n')
  // DP guard: beyond ~500k cells fall back to naive alignment.
  if (al.length * bl.length > 500_000) {
    const n = Math.max(al.length, bl.length)
    const rows: DiffRow[] = []
    for (let i = 0; i < n; i++) {
      const l = al[i] ?? null
      const r = bl[i] ?? null
      rows.push({
        left: l,
        right: r,
        type: l === r ? 'same' : l === null ? 'add' : r === null ? 'del' : 'change',
        leftNo: l === null ? null : i + 1,
        rightNo: r === null ? null : i + 1,
      })
    }
    return rows
  }

  const n = al.length
  const m = bl.length
  // LCS lengths
  const dp: Int32Array = new Int32Array((n + 1) * (m + 1))
  const at = (i: number, j: number) => i * (m + 1) + j
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[at(i, j)] =
        al[i] === bl[j]
          ? dp[at(i + 1, j + 1)] + 1
          : Math.max(dp[at(i + 1, j)], dp[at(i, j + 1)])
    }
  }
  // Walk: collect op runs
  const rows: DiffRow[] = []
  let i = 0
  let j = 0
  let dels: number[] = []
  let adds: number[] = []
  const flush = () => {
    const k = Math.max(dels.length, adds.length)
    for (let t = 0; t < k; t++) {
      const di = dels[t]
      const aj = adds[t]
      rows.push({
        left: di !== undefined ? al[di] : null,
        right: aj !== undefined ? bl[aj] : null,
        type: di !== undefined && aj !== undefined ? 'change' : di !== undefined ? 'del' : 'add',
        leftNo: di !== undefined ? di + 1 : null,
        rightNo: aj !== undefined ? aj + 1 : null,
      })
    }
    dels = []
    adds = []
  }
  while (i < n && j < m) {
    if (al[i] === bl[j]) {
      flush()
      rows.push({ left: al[i], right: bl[j], type: 'same', leftNo: i + 1, rightNo: j + 1 })
      i++
      j++
    } else if (dp[at(i + 1, j)] >= dp[at(i, j + 1)]) {
      dels.push(i)
      i++
    } else {
      adds.push(j)
      j++
    }
  }
  while (i < n) dels.push(i++)
  while (j < m) adds.push(j++)
  flush()
  return rows
}
