# Argus 專案規則

## 專案定位

Argus 是 SaaS 級網站健檢平台。使用者輸入 URL 後，系統執行同網域爬蟲、SEO/AEO/GEO/被動資安掃描，並輸出互動式工作區、Word 報告與可複製的問題描述 prompt。系統只提供問題描述與修補方向，不直接產生修復程式碼。

## 開工前必讀

每次處理 Argus 任務前，依序讀取：

1. `CLAUDE.md`
2. `Project_說明.md`
3. `開發計畫.md`
4. `skills/argus-project/SKILL.md`
5. 本 skill 的 relevant reference

若任務涉及子目錄，額外查找適用的 `AGENTS.md`。

## 使用者新增規則

- 每做約 20 分鐘，更新 `.sisyphus/argus-handoff.local.md`，避免長任務失去上下文。
- 做之前先思考是否符合使用者真正需要；不要只完成表面文字。
- 製作時要詳細閱讀規則、開發計畫與 Project 說明。
- 做完後測試；每找到 `n` 個與本次改動相關錯誤，新增至少 `n*2` 個不同類型測試。
- 所有與專案有關的重要規則、決策、地雷、API provider 狀態與參考資料，優先記錄在專案內 skill 或 `.sisyphus` 交接檔。
- 禁止污染全域環境；所有依賴、瀏覽器與建置產物都必須留在專案目錄、`.venv` 或 Docker 容器內。
- Playwright Chromium 必須安裝到專案 `.ms-playwright`，不能使用使用者層級 `AppData/Local/ms-playwright`。

## 環境隔離規則

- Python：使用 `uv sync` / `uv run`，不得使用全域 `pip install`。
- Node：只在 `frontend/` 執行 `npm.cmd install`，不得使用 `npm -g`。
- Playwright：安裝前必須設定 `PLAYWRIGHT_BROWSERS_PATH=.ms-playwright`。
- Docker：允許作為隔離方案，但不得把秘密寫入 image 或 compose 檔。
- 若命令可能寫入全域快取或使用者層級目錄，先檢查文件與環境變數，不可直接執行。

## 測試規則

優先順序：

1. 最小可重現測試或最接近改動面的測試。
2. 對應層級測試：Python/Django 用 `uv run` 或專案測試；前端用既有 lint/test/build；API 改動需直打端點。
3. 若找到 `n` 個本次改動導致或暴露的有效錯誤，補 `n*2` 個不同類型測試，例如 unit、integration、regression、edge case、security boundary、serialization、UI state。
4. 若專案尚無測試框架，不新增大型測試架構；先記錄可執行手動測試清單與建議測試落點。

不要為無關既有錯誤做大範圍修復；可在交接與 final 中標明。

## 法律與倫理硬性要求

- 使用者送出 URL 前，必須確認「擁有網站或已獲書面授權測試」；後端需記錄 IP、timestamp、user_id。
- 爬蟲預設 same-origin、最大深度 3、最大頁數 50、遵守 `robots.txt`。
- 資安預設被動偵測，只分析 header、HTML、cookie flags、CSP、CSRF token 缺失、混合內容、`.git`/`.env` HEAD 檢查。
- 主動測試必須額外授權、RPS ≤ 2、只使用無破壞 payload，並加 User-Agent：`SiteSense-AI-Scanner/1.0 (authorized-audit)`。
- 明顯第三方網站需 UI 警告並要求重新確認。

## 敏感資訊規則

- `.env`、`GoogleCloud_ApiKey.json`、API Key、Token、密碼、私鑰只可用於本機測試，不可輸出值。
- 記錄時只寫變數名稱、provider、通過/失敗狀態、HTTP 狀態類型，不寫原始請求/回應 body。
- `.gitignore` 必須保護 `.env`、`GoogleCloud_ApiKey.json`、本機交接檔與常見 build/dependency 目錄。

## 部署與協作安全規則（公網上線後）

- **部署現況**：已上線公網 `https://xn--gst.tw/`（部署在另一台電腦）；GitHub repo `https://github.com/Djude1/Argus.git` 與部署機**共用**；repo 內**有其他組員同時開發**。任何 push 都是對外、會影響線上環境與他人的操作。
- **push / commit 前強制（全部滿足才可 push）**：
  1. commit 訊息詳細標示「改了什麼 + 為什麼」，分點列出，禁止一行模糊帶過。
  2. 只 stage 自己這次的改動（用明確檔案路徑，**禁止 `git add .` / `-A`**），避免夾帶他人或無關變更。
  3. 先驗證無問題：依改動範圍跑相關測試 / `uv run python backend/manage.py check` / 前端 build，並 `git diff --staged` 逐項審視，確認沒壞東西、沒夾帶機密。
  4. 取得使用者明確同意才 push，**不自行 push**。
- **一定不能 push**：`.sisyphus/*.local.md` 本機交接檔、`CLAUDE.local.md`、`.env`、`GoogleCloud_ApiKey.json`、任何金鑰或硬編碼秘密。
- **機器專屬設定**（是否測試機、RTK 實際安裝路徑等）放 `CLAUDE.local.md`（gitignored），不寫進會被 push 的團隊共用檔，以免跨機器 drift。

## 交接檔格式

更新 `.sisyphus/argus-handoff.local.md` 時使用：

```markdown
# Argus Handoff

## Timestamp
- YYYY-MM-DD HH:mm TZ

## Current Goal
- ...

## Context Read
- ...

## Decisions
- ...

## Files Changed
- ...

## Validation
- ...

## Error Count And Added Tests
- errors_found: 0
- tests_added_required: 0
- tests_added_done: ...

## API Provider Status
- provider/model status only; no secrets

## Next Steps
- ...
```
