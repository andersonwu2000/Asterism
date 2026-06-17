# Librarian — 把已證 Problem 整理成可重用的 Library（設計手冊 v0.3）

操作 / 設計手冊。`docs/internal/`（gitignored）——會隨實作 drift；穩定後畢業成 committed
`docs/librarian.md`。最後更新：2026-06-03（**v0.3 大改：砍 dedup / cleanup,migrate+bridge 全機械,
classify 是唯一 agentic 步**。v0.2 的全 agentic 五階段鏈降級為 §8 歷史）。

> **一句話（v0.3）**：Librarian 把一個已證 Problem 的 proof forest,**忠實、機械地**搬成一個
> 自足的 `Library/` 依賴圖,供**跨題引用**。唯一需要語意判斷的是「怎麼分檔」(classify);
> 其餘全部確定性機械化。**不追求 mathlib-PR 乾淨度**(那是日後 opt-in 的事)。

---

## 0. 目標與取捨（v0.3）

`Library/` = **跨題可重用的 lemma 倉**。

- **主目標(做)**：goal #1 — 後續題目能 import 前面題目證出的 lemma。要的是「自足 + 可建置 + 意義不變」。
- **延後(先不做)**：goal #2 — mathlib-PR-ready(去重、殺 unused hyp、idiom 化)。這是 v0.2 的
  dedup/cleanup 在做的事,**high-variance、脆弱、會死結**(2026-06-03 實證),故 v0.3 整段砍掉,
  日後要 PR 時再單獨 opt-in 跑。

### v0.2 → v0.3 為什麼這樣改（核心因果）
migrate 之所以需要 LLM 補洞,**根源是 dedup**:drop/merge/cite 拿掉某些 sibling → 引用點接不上 →
變 `sorry` 洞 → 才要 LLM。**全部 keep 後,每個 proof-term 引用都指向一個同樣搬進 Library 的 kept
decl → 機械 relabel 能解析所有引用 → 無洞 → 不需要 LLM。** 「不 dedup」與「migrate 純機械」是
同一件事的因果,不是兩個獨立決定。

代價(已接受)：Library 囉嗦——重造的 mathlib 輪子、scaffolding 中間步、近重複 sibling 全保留,
名字帶框架味。但對跨題引用完全夠用(import 得到、用得了)。重造輪子的**根治**是 rule #9(給
Forward 真 mathlib 搜尋),dedup 本來就只是兜底;砍兜底 = 接受 staging 倉裡有輪子。

---

## 1. 北極星不變量（不變,仍是 v0.3 的硬約束）

> **Library 是自足的依賴圖。葉子檔只 import Mathlib；內部檔 import Mathlib + 其他 Library 檔。**

是整個 Library **閉包**的性質。⚠️ **閉包不變量與「非重造」正交**:一個只 import mathlib、build 過
的檔仍可能是重造的輪子。v0.3 **明確只保證閉包(脫離框架特化),不保證原創性**——原創性檢查(dedup)
已移除,接受之。

---

## 2. 兩道核心 gate（framework 端、確定性,保留）

### Gate A — import-closure
每個 Library 檔的 `import` ⊆ {Mathlib.*, 其他 Library.*}。出現 `Problems.*` / `Defs` → reject。純文本 + build 驗。

### Gate B — root re-derivation（「秒殺 root」,Defs-free）★ 定海神針
原始 `main`(已 `integrity_verified=1`)能從只 import Library 的探針一行推出:
```
import Library.<...>          -- 只引 Library(無 Defs、無 Problems)
theorem main : 〈statement〉 := 〈一行:Library.<keystone>〉
```
- 擋「搬運偷偷改弱」:能推回 main → Lean kernel 證明 Library ≥ main 同強,無需人肉檢查。
- **v0.3 機械化**:全 keep + 機械搬運後 `main` 的 keystone 也在 Library,bridge 只需**機械**寫探針
  (寫→build+axiom→刪),**不再 spawn agent**(原 task #80「retire bridge direct-edit → pure probe」)。
  探針不 commit 進 Library。

---

## 3. ★ v0.3 流程（一個 Problem 進 Library）

```
 [Problem: root proved + integrity_verified=1 + Manifest library:true]
                              │
                              ▼
  Step 0  INVENTORY      [framework, 機械]
     讀 DB goals + strategy_subgoals → 每 decl {slug, deps, refs} + 抽 Defs decls。
     全部標 keep(無 dedup)。產 annotated 底稿。
                              │
                              ▼
  Step 1  CLASSIFY       [Librarian agent — 唯一語意判斷步]
     把所有 decl 分檔/目錄(語意分群、mathlib-ish layout)+ 檔內序(file_order)+ 跨檔依賴。
     verify_classify: 涵蓋全部 decl、無環、import 皆 Library。
                              │  file DAG 拓樸序
                              ▼
  Step 2  MIGRATE        [framework, 純機械, 無 spawn]
     per-file 拓樸序(依賴檔先)。每檔機械 relabel:
       - namespace 改 Library.<...>;drop `import Problems.*` / Defs import
       - 內聯 alias → strategy body(語法替換)
       - 所有 proof-term 引用都指向 kept sibling(全 keep)→ 直接 relabel,無洞
     commit gate: Gate A + 整檔 build + axiom(+ Gate D def-equiv)。
     ⚠️ 機械搬不動的(極少數 alias-body 內聯邊角)→ **hard-fail + flag operator**,不回退 LLM
        (保持確定性;真的常見再考慮「僅該 decl 的最小 LLM fallback」)。
                              │  全檔 migrated
                              ▼
  Step 3  BRIDGE (Gate B) [framework, 機械探針]
     機械寫 `import Library.<...>; theorem main := Library.<keystone>` → build + axiom →
     過了 framework 寫 INDEX(= done-marker, 含 Gate B provenance)。探針不留。
```

工作種類分工(v0.3)：
| 層 | 負責 |
|---|---|
| **Framework**(確定性) | inventory；migrate(relabel + build gate)；Gate A/B/D + axiom；機械 bridge 探針；INDEX |
| **Librarian agent**(判斷) | **只有 classify**(分檔/版面) |
| **Strategist** | (v0.3 暫無角色;dedup review 已隨 dedup 移除) |

---

## 4. 砍掉了什麼 + 日後怎麼加回（增量路線）

- **dedup(砍)**:全 keep。日後若要去重,做成 **opt-in 的後置 pass**(在 migrated Library 上跑,
  不在主鏈),且要先解決它的 high-variance(同輸入 81↔22)——例如給穩定錨、或只在「明確跨題重用」時觸發。
- **cleanup(砍)**:PR-readiness + 簽名改寫,也是 2026-06-03 死結來源(改簽名要更新還沒 migrate 的
  下游 call-site)。日後要 PR 時做成**手動/opt-in 的全 migrate 後一次性 pass**,reverse-topo(importer
  先 clean、被依賴者後 clean),call-site 都存在才不會死結。
  → **v0.4 重新設計(2026-06-06):見 `docs/archive/design/librarian_cleanup.md`**(分階段精修 campaign、
  staging 模型、曝光門檻 = axiom+Gate B、cleanliness best-effort+watermark;dedup 一節 user 設計中)。
- **migrate Phase 2 LLM(砍)**:見 §0 因果,全 keep 後不需要。
- 原則:「**先只給 Librarian 做 classify,以後再慢慢加**」——主鏈保持儘量機械、確定性;新功能一律
  先以 opt-in 後置 pass 形式加,別塞回主鏈破壞可重現性。

---

## 5. 實作狀態（2026-06-03）

- **現況 = v0.2 的全 agentic 五階段鏈**(`Tooling/pipeline/librarian.py`:dedup/classify/migrate/
  cleanup/bridge work-kind)。v0.3 **尚未實作**。
- v0.3 落地的 code 改動(待做,需 user 點頭):
  1. **derive 路由**:lifecycle 改 candidate→classified→migrated→(跳 cleanup)→INDEX。inventory 直接把
     decl 標 keep+classified-pending(無 dedup state);`_derive_librarian_work` 拿掉 dedup/cleanup 分支。
  2. **classify**:輸入從「kept decls」改成「全部 decls」;prompt/verify_classify 對齊(涵蓋全部、無環)。
  3. **migrate**:`_run_migrate` 拿掉 Phase 2 spawn + seed 洞;純機械 relabel,搬不動 → hard-fail+flag。
  4. **cleanup**:從 derive 拿掉(migrated → 直接 bridge);code 留 dormant 供日後 opt-in。
  5. **bridge**:`_run_bridge` 改純機械探針(no spawn);沿用 `check_root_rederivation`。
  6. **dispatcher/#92**:librarian 幾乎全機械後,#92 檔級並行價值降低(機械 migrate 很快),但無害可留;
     Bug A/B(daemon 自啟 + 退出閘認得 librarian pending)仍需要。
- 已 commit 的相關基礎(留用):Gate A/B(`check_root_rederivation`)、Gate D、inventory、relabel.py
  的機械 relabel、Defs 統一(Defs decl 當 sibling 搬)、#92 Bug A/B 修復、jordan Manifest `library:true`。

---

## 6. 待商榷 / 殘留風險

- **alias→strategy body 內聯的機械可行性**:plan v0.2 §7 標只在 Jordan 樣本驗過。v0.3 不 dedup 消掉了
  non-keep 洞,但 alias-body 內聯仍是純語法操作、極少數可能卡 → hard-fail+flag(見 §3 Step 2)。他題待驗。
- **classify 的負擔/variance**:不 dedup 後 classify 要排全部 decl(Jordan 144,非 22),agentic layout
  變重、有 variance。先留 agentic(語意需要);若 variance 痛,再考慮機械分組(usage-SCC)兜底。
- **discoverability**:Library 含全部 decl(含內部步),跨題搜尋有噪音。日後加便宜的「可重用性」標記,非核心。
- **可重入**:mathlib 補上新概念後,可選 re-index;v0.3 主鏈不處理。

---

## 7. （保留）mathlib 形狀的兩種「保意義」情況 — 供日後 cleanup/PR pass 參考
- (a) 內部 brick-splice:重造的 mathlib brick 換 citation,build 過即保意義。
- (b) 頂層 statement 改 canonical 形:需 Gate B root re-derivation 橋(v0.3 仍在,機械化)。

---

## 8. 附錄 — v0.2（已被 v0.3 取代的全 agentic 五階段鏈）

v0.2 是「inventory → **dedup**(agent 判 keep/drop/cite/merge)→ classify → **migrate**(機械 Phase 1 +
build-gate 分流 + LLM Phase 2 補洞)→ **cleanup**(agent 改簽名 PR 化)→ **bridge**(agent 重推 root)」。
核心發現曾是「搬運大部分機械、由 build gate 分流哪些要 LLM」。

**為何退役(2026-06-03 實證)**:
- dedup high-variance:同 prompt 同輸入,Jordan keep 81↔22,Library 形狀每輪不同、不可重現。
- migrate 補洞、cleanup 改簽名都是脆弱 agentic 步,failure mode 多。
- cleanup 改簽名要更新下游 call-site,但下游還沒 migrate(磁碟不存在)→ **順序死結**(cleanup 緊接
  migrate 與「migrate 對著 cleaned 依賴」互斥)。
- 結論:把「整理乾淨(goal #2)」和「能用(goal #1)」綁在一條全 agentic 鏈裡,讓便宜可靠的 goal #1
  被昂貴脆弱的 goal #2 拖垮。v0.3 拆開:主鏈只做 goal #1、機械化;goal #2 日後 opt-in。

完整 v0.2 機制細節(三階段 build-gate 分流、5 種 verdict 重定向表、needs-upstream cascade、各 commit
hash)見 git 歷史本檔 v0.2 版本。
