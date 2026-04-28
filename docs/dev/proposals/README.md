# Proposals

未來開發的 RFC / 設計討論。**不是 frozen spec**——架構決策落 `docs/architecture/`、phase 計畫落 `docs/dev/phaseN_*.md`。

本目錄專收：
- 跨 phase 的設計討論（不屬單一 phase）
- 架構擴張提案（最終目標 PR 進 `docs/architecture/`）
- 當前 phase 不做、但已有共識的「下個 milestone 後該補」項目

每篇 proposal 含：背景 / 設計 / 風險 / 實作時機 / 上線後 architecture spec PR 範圍。

實作完成 → spec PR 進 architecture 後、proposal 標 `superseded by architecture §X`、本目錄保留作歷史紀錄。

## 當前 proposals

- [runtime-config-layering.md](runtime-config-layering.md) — 全域 config 檔 + per-Problem runtime override（架構 §8 配置模型擴張）
- [proof-integrity-defense.md](proof-integrity-defense.md) — `#print axioms` 之外的 framework-side 防偽檢查（statement_hash 比對 / hard reject list / `.lake/` permission / IO grep）
