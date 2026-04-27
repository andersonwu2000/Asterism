# 任務：{任務名稱}

## 工作目錄

`{workspace 絕對路徑}`

## 專案概述

{專案是什麼、用什麼技術、做什麼事。一段即可。}

## 目標

{任務目標的簡要描述。由代理自行判斷改進方向和優先順序。}

## 終止條件

{例如：達到 X 指標後停止、最多跑 N 輪、時間上限等}

## Note（可選）

{在**運作過程中可修改**，提供指示}

## 參考文件（可選）

{可供參考的文件、目錄或圖片}

## 唯讀檔案（可選）

{不可修改的檔案，例如 `package.json`、`tsconfig.json`}

## 邊界（可選）

{不該做什麼、不該碰什麼、不該引入什麼。例如：不加新依賴、不改公開 API 簽名、不做大規模重構}

## 指標（可選）

以可執行的指令為準：
- **主要**：{例如 `bun test` 全部通過}
- **次要**：{例如 `bun tsc --noEmit` 無錯誤}

## Runtime 行為指令（可選）

用於觀察 runtime 行為。用於研究專案需求和審計。
若未填寫，Orchestrator 會根據專案結構自動推斷。

```bash
# {觀察指令，依專案類型而異，例如：}
# Web app:    npx playwright screenshot http://localhost:3000 out.png
# API:        curl -s localhost:8080/api/status | jq .
# CLI:        echo "test input" | node cli.js --verbose
# Service:    tail -20 logs/app.log
# Test:       bun test --verbose 2>&1 | tail -50
```

## 模型（可選）

若未指定，使用 claude 預設模型。

| 角色 | 模型 |
|------|------|
| Auditor | {例如 claude-opus-4-6} |
| Executor | {例如 claude-sonnet-4-6} |

## 需審批的操作（可選，補充 roles/executor.md 預設清單）

{例如：修改 database schema、變更 API 介面、碰 config/ 目錄等}
