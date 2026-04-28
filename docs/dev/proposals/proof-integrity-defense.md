# Proof integrity defense — `#print axioms` 之外的 framework-side 防偽

## 目的

architecture v3 §7.1 用 `#print axioms <thm>` 構造 trust_set + 比對 Problem.axioms whitelist 作為 verdict accept rule。**這個機制本身 kernel-trusted、無法被欺騙**——但 framework 套在它外面的「檢查管線」有幾個 surface area，agent 真要繞有幾條路可走。

本文列出風險矩陣 + 5 條補強建議，按 cost-benefit 排優先。

## `#print axioms` 本身為什麼可信

`#print axioms <thm>` 是 Lean kernel 直接走 proof term 依賴鏈、列出所有 transitively 引用的 axiom name。**繞它要動 Lean 編譯器本體**——agent 拿不到那層權限。

包括：
- `propext` / `Quot.sound` / `Classical.choice` — 標準三公理
- `sorryAx` — `sorry` tactic 真實名字（一定看得到）
- `Lean.ofReduceBool` — `native_decide` 引入
- `lcProof` — `unsafeCast` 等 unsafe primitive 引入
- 任何 user 寫 `axiom foo : ...` 或 `opaque foo : ...` 都顯式列出

只要 Problem.axioms 比對 strict、不漏網、就 sound。

## Framework 套在外的檢查管線：6 個攻擊面

按真實攻擊面排——high risk 到低：

### 攻擊面 1：agent 寫檔到 staging 外（命名 axiom 偽裝）— HIGH

**情境 A**：agent 在 `Defs.lean` 加 `axiom my_cheat : G`、`theorem g := my_cheat`、`#print axioms g` 看到 `my_cheat`、whitelist 不含 → reject ✅

**情境 B（危險）**：agent 用「看起來合法」的 axiom 名直接 hijack：
```lean
axiom propext : ∀ {p q : Prop}, (p ↔ q) → p = q  -- 偽裝成標準
axiom Classical.choice : ...                       -- 直接 hijack 已知名
theorem g := Classical.choice
```
`#print axioms g` 看到 `Classical.choice` → whitelist 通過 ✅ → **被騙**

**現有防線**：
- architecture §7.2「Agent 修改範圍」：agent 只能寫 `Goals/<G>/Staging/<p_uuid>/`、`Defs.lean` 在 staging 外、唯讀
- 執行：`claude --add-dir` 限制 + agent 結束後 git status 等價檢查
- 違反 → 該 stage 視為 failed → retry

**漏洞**：
- `claude --add-dir` 是 claude CLI 自己的 scope 機制
- P5 spike-019 顯示 gemini / codex CLI 沒等價 flag、靠 git status 兜底
- git status 兜底 **不會偵測 gitignored 檔案**（`.lake/` / `*.olean`）
- gemini / codex provider 切過去後 scope-isolation 弱化

### 攻擊面 2：tampering `.lake/` cache — MEDIUM-HIGH

**情境**：
- `.lake/` 內存 Mathlib oleans（已編譯 Lean 物件檔）
- agent 寫 evil olean 覆蓋 Mathlib 某 lemma 編譯結果
- type signature 不變、實際 implementation 改成「永遠回 true」
- `theorem g := mathlib_lemma_now_lying` proof 過 kernel
- `#print axioms` 看當前 olean 依賴、被替換的看起來合法

**現有防線**：未確認，C45 codebase 應檢查 `.lake/` 是否真 read-only（filesystem permission，不只 gitignored）

### 攻擊面 3：`native_decide` / unsafe primitive 引入額外 axiom — MEDIUM

**情境**：
```lean
theorem g : large_combinatorial_property := by native_decide
```
`#print axioms g` 顯示 `Lean.ofReduceBool` axiom——「**信任編譯後的 native code**」。若 native code 有 bug 或被 tampered → verify 過了但結果可能錯。

**現有防線**：Problem.axioms 是否含 `Lean.ofReduceBool` 決定。v3 §8.2 「Foundational 層」沒明說、user 範例只列三公理。

**漏洞**：
- user 不知道 `Lean.ofReduceBool` 存在 → 沒寫進 axioms、也沒寫進 reject 清單
- 框架 default whitelist 若放寬包含 Mathlib 常見 axiom（v3 §8.2 提的「放寬」範例）→ 可能不小心包進 `Lean.ofReduceBool`

### 攻擊面 4：staging 內 statement mutation — MEDIUM

**情境**：
- Goal `<slug>.lean` 原本：`theorem g : <hard_statement> := sorry`
- agent 在 staging 寫 proof body 換 sorry → 同時改 statement 為 `theorem g : True := trivial`
- `#print axioms g` 全空（trivial proof）→ pass
- cascade 標 G proved → user 以為 hard_statement 證了

**現有防線**：
- architecture §7.2 staging 外唯讀 → agent 不能改正式檔的 statement
- BUT：agent 寫的是 staging 內 `<slug>.lean`、commit 階段 mv 到正式位置——**commit 不檢查 statement 是否變了**
- v3 §9.1 `goals.statement_hash` column 存在但**沒寫「commit 時對比」這條檢查**

**漏洞**：
- `statement_hash` 在 P2 寫入時計算、之後沒人對比
- agent staging 寫的 `<slug>.lean` 可含**不同 statement** → mv 覆蓋原檔、cascade 跑 `#print axioms` 用新檔 → kernel 驗的是新 statement、不是 user 注入的

### 攻擊面 5：whitelist 解析 bug — MEDIUM

**情境**：
- META.md `axioms: [propext, Quot.sound, Classical.choice]`
- meta.py YAML parser 大小寫敏感？空白敏感？unicode 同形字？
- `#print axioms` 輸出 `propext`、meta.py 比對 `propext ` (尾巴空白) → 比對 fail（false negative、user 困擾）
- 反向：agent 寫 axiom `Propext`（大寫 P）、meta.py case-insensitive 比對 → pass（false positive、安全風險）

**現有防線**：要看 `Tooling/meta.py` + `Tooling/trust.py` 實作的 normalize / case 處理

### 攻擊面 6：proof 用了 sorry/lcProof 但沒 catch — VERY LOW

**情境**：agent 寫 `theorem g := by exact ?_`（缺 proof、用 elaboration hole）或用 `Lean.Elab.Term.unsafeCoe` 等

**現有防線**：`sorryAx` / `lcProof` 都 kernel-known axiom、`#print axioms` 一定列、whitelist 預設不含 → reject

**幾乎不可能繞**——除非 Lean kernel 本身有 bug。

### 攻擊面 7：`#eval IO.*` injection — LOW

**情境**：agent 在 staging .lean 寫 `#eval IO.system "rm -rf /"` 之類——lake env lean 跑時真會執行

**現有防線**：未明說。staging .lean 走 elab + type-check、`#eval` 是 explicit command 才跑，但 nothing 阻 agent 寫 `#eval`

## 風險矩陣

| # | 攻擊面 | Likelihood | Impact | Asterism 現有防線 | 補強建議 |
|---|---|---|---|---|---|
| 1 | 寫檔 staging 外（命名 axiom 偽裝） | 中 | 高 | `--add-dir` + git status 兜底 | 補 gemini/codex 同等 scope；statement_hash commit 檢查 |
| 2 | `.lake/` olean tampering | 低 | 高 | 未確認 | `.lake/` filesystem read-only |
| 3 | `Lean.ofReduceBool` (`native_decide`) | 中 | 中 | 無顯式 reject | framework default reject、user opt-in |
| 4 | staging 內 statement mutation | 中 | 高 | statement_hash 寫但**沒對比** | commit stage 對比 hash |
| 5 | whitelist 解析 bug | 低 | 中 | 看 meta.py/trust.py 實作 | normalize + case-sensitive + unit test |
| 6 | sorry/lcProof 漏網 | 極低 | 高 | `#print axioms` 必抓 | 無需額外 |
| 7 | `#eval IO.*` injection | 低 | 高 | 未明說 | self_verify 前 grep reject |

## 5 條補強建議（依 cost-benefit 排）

### 1. `commit` stage 對 statement_hash 比對（攻擊面 4）

**最便宜、最高 impact**。

architecture §9.1 `goals.statement_hash` 已存在。Backward / Builder commit 前：

```python
new_hash = sha256(staging_file.read_text())
if new_hash != goal.statement_hash:
    raise FatalError(f"statement mutation detected: goal={goal_id}")
```

5 line 改動、堵掉「agent 改 statement 同時寫 trivial proof」這條最危險的繞線。

### 2. Framework default hard reject list（攻擊面 3）

`Tooling/trust.py` 加：

```python
# Framework-wide reject list (independent of Problem.axioms)
# These axioms compromise verification trustworthiness if accepted.
ASTERISM_HARD_REJECT_AXIOMS = {
    "sorryAx",                          # sorry
    "Lean.ofReduceBool",                # native_decide trusts compiled code
    "lcProof",                          # unsafeCast bypass
    "Classical.indefiniteDescription",   # 不是 strictly 不安全、但比 choice 強、強制 user opt-in
}
```

trust_set 含任一 hard reject → 直接 fatal halt + alert user，**不靠 Problem.axioms 是否含**。

User 真要 native_decide？編 framework config（或 P7+ per-Problem META.md）顯式 opt-in、留 audit trail。

### 3. `.lake/` filesystem read-only（攻擊面 2）

P5 spike-019 順帶驗：
```bash
chmod -R a-w .lake/
```
agent run 完 git status check + permission check（`.lake/` 應永遠 read-only）。

若 lake build 自身需要 write `.lake/`（rebuild），用 lake daemon mode + 隔離 agent 不能 invoke lake build 直接寫。

### 4. Staging .lean 寫進前 grep 反 IO injection（攻擊面 7）

`Tooling/stages/self_verify.py` 在 lake env lean 跑前：

```python
forbidden_patterns = [
    r'#eval\s', r'IO\.system', r'IO\.FS\.', r'unsafeIO',
    r'@\[implemented_by', r'@\[extern', r'init_quot',
]
for pattern in forbidden_patterns:
    if re.search(pattern, content):
        raise StageError(f"forbidden pattern in staging: {pattern}")
```

⚠️ 注意：v3 §7.4「禁 regex parse Lean 源碼」是針對 hypothesis carry validator——**這條是 security check 不是語意 validator**，regex 守安全合理（false positive 寧可 reject、不放過）。明說兩用途 distinguishable。

### 5. Whitelist 解析的 unit test（攻擊面 5）

`Tooling/tests/test_meta.py` / `test_trust.py` 加 evil-by-typo case：
- `axioms: [Propext]`（大寫 P，meta.py 應 reject 或視為不同 axiom）
- `axioms: ['propext ']`（尾巴空白）
- `axioms: [propext, propext]`（重複）
- `axioms: ['classical.choice']`（小寫 c，meta.py 應 reject）

確保 **whitelist 比對 strict、case-sensitive、whitespace-trimmed**。

## 不該擔心 / 過度設計的事

1. **Lean kernel bug** — 不是 framework 該防、假設 kernel sound
2. **`opaque` def 偽裝** — `#print axioms` 看得到、whitelist 抓
3. **tactic 不健全** — kernel 一定 re-check 最終 proof term
4. **proof 形式上的 trick**（`exact?` / `polyrith` 等）— 任何 tactic 最終產出都過 kernel
5. **Mathlib 內 `axiom`** — 都已知、列入 ASTERISM_HARD_REJECT 或 Problem opt-in

## P5 spike-019（gemini / codex scope-isolation）的 carry-over

gemini / codex 沒有 claude `--add-dir` 等價 → 純靠 git status 兜底。**多 provider 的安全 floor 由最弱 provider 決定**。

如果 spike-019 結果顯示某 provider 的 scope-isolation 弱：
- 該 provider 排在 fallback chain 末位
- 對 high-trust task（commit 有 verdict effect 的 stage）禁用該 provider
- 或乾脆從 chain 移除

## 實作時機

5 條補強建議按 cost-benefit 排序：

| 優先 | 補強 | 工作量 | 適合 phase |
|---|---|---|---|
| 1 | statement_hash commit 比對 | 5 line + 1 test | 任何 phase 隨時補（建議 P4 結束前） |
| 2 | Framework hard reject list | 半天 + 1 test | P4 結束前（trust set 機制成熟時） |
| 3 | `.lake/` read-only | 半天（chmod + permission check） | P5 spike-019 時順帶 |
| 4 | self_verify IO grep | 1 hr + 1 test | P2 結束前（self_verify 機制建立時）|
| 5 | Whitelist 解析 unit test | 1 hr | P2 結束前 |

**最該優先**：(1) statement_hash 比對，因為這是 framework 已有 column、commit stage 已存在、加 5 line 即可堵最大攻擊面。

## 後續 architecture spec PR 範圍

實作完成後 PR `docs/architecture/`：

- `architecture.md §7` 新增 §7.6「Framework hard reject axiom list」段落（Asterism 級拒絕、不靠 Problem.axioms）
- `architecture.md §7` 新增 §7.7「Statement integrity」段落（commit stage statement_hash 對比）
- `architecture_impl.md §6.2` self_verify 段補「IO injection grep 預檢」
- `architecture_impl.md §5.3` accept_rule 補「ASTERISM_HARD_REJECT 第一道過濾、優先於 Problem.axioms 比對」

## 參考

- architecture v3 §7.1 Trust set 與 axiom whitelist
- architecture v3 §7.2 Agent 修改範圍
- architecture v3 §9.1 `goals.statement_hash`
- architecture impl §5.2「從 #print axioms 構造」
- architecture impl §5.3 Accept rule 分流
- P5 spike-019 gemini / codex CLI scope-isolation 對齊（待跑）
