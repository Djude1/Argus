# Argus Project Memory

## Purpose

本檔記錄 Argus 專案可公開的工作記憶與交接規則。禁止寫入 API Key、Token、密碼、私鑰、完整憑證 JSON、個資或原始敏感錯誤內容。

## Current Project Understanding

- Argus 是 SaaS 級網站健檢平台，MVP 包含同網域爬蟲、SEO/AEO/GEO/被動資安掃描、互動式截圖高光工作區、Word 報告與 AI handoff prompt。
- 技術棧固定：React 18/Vite/Tailwind/Zustand/Axios、Django 5/DRF/SimpleJWT、Celery/Redis、Playwright Python async、SQLite dev/PostgreSQL prod、python-docx、Docker Compose。
- Phase 2 才加入 LLM Agent/tool calling；目前 provider 決策以 GLM/MiniMax/Gemini 實測可用性為準。

## Persistent Rules Added By User

- 所有專案重要內容、決策、地雷、API provider 狀態與參考資料，寫進專案內 skill 或 `.sisyphus` 記憶。
- 每做約 20 分鐘，更新 `.sisyphus/argus-handoff.local.md`。
- 做之前先判斷是否符合使用者真正需求。
- 做完後測試；每找到 `n` 個有效錯誤，新增 `n*2` 個不同類型測試。
- 製作時詳細閱讀 `CLAUDE.md`、`開發計畫.md`、`Project_說明.md`。
- GLM API 出問題時，改用 Gemini 或 MiniMax。
- 使用 API Key 前先測試該 key 有哪些模型可用，並選最適合專題的模型。
- 使用者已提供 MiniMax 設定。

## API Status Snapshot

2026-05-20 安全測試摘要：

- MiniMax：models 授權通過，tool-calling smoke test 通過。
- Google Gemini：models 授權通過。
- GLM：`glm-4.7-flash` 與 `glm-4.5-flash` chat/tool-calling smoke test 通過；多數較高階模型當下回 HTTP 429，舊 flash 版本回 HTTP 400。
- Google service account JSON：欄位形狀正確。

每次實際呼叫 API 前仍需重新測試；不得輸出秘密值。

## Project Skill

專案內 Skill 位置：

- `skills/argus-project/SKILL.md`
- `skills/argus-project/references/project-rules.md`
- `skills/argus-project/references/api-provider-workflow.md`
- `skills/argus-project/references/external-references.md`
- `skills/argus-project/references/technology-adoption.md`

後續 Argus 任務應先讀取上述檔案。

## External Technology Adoption

- 已將使用者提供的外部連結轉成 `skills/argus-project/references/technology-adoption.md`。
- MVP 採納：Scrapling 的 crawler reliability 思路、GEOFlow 的任務/後台/provider fallback 思路、aeo-site/Optimeyes 的 AEO score 與 Top Actions、awesome-geo 的 FAST/GEO technical checklist、RTK 的輸出壓縮。
- Phase 2/3 延後：RAG/知識庫、keyword tracking、competitor analysis、brand mention/citation monitoring、多語言與 API integration。
- 明確不採納：反爬繞過、指紋偽裝、代理池規避、外部替代技術棧、自動產生修復程式碼、批量內容污染。

## Consistency Fixes

- 2026-05-20：統一 AI Provider 描述為 MiniMax-M2.7 優先、GLM `glm-4.7-flash` / `glm-4.5-flash` 第二順位、Gemini 分析備援；Project 說明不再要求 OpenRouter/Hermes 模型 endpoint。
- 2026-05-20：修正 `開發計畫.md` 技術棧表格欄位數，避免 Markdown 表格解析錯誤。
- 2026-05-20：統一資料模型命名為 `Page`，移除採納矩陣中的 `CrawledPage` 命名。
- 2026-05-21：修正 `開發計畫.md` 過時清單——截圖 API、robots.txt、前端授權勾選、自訂 User-Agent、same-origin enforcement、scoring 等已完成項目原誤標為未完成。

## Implementation Snapshot

- 2026-05-20：建立 Django 後端骨架於 `backend/`，包含 `config`、`accounts`、`scans` app。
- 2026-05-20：新增核心模型 `User`、`ScanJob`、`Page`、`Finding`、`AgentSession`、`AgentStep`、`AuthorizationConsent`，並產生初始 migrations。
- 2026-05-20：新增 SimpleJWT token endpoint、ScanJob 建立/list/retrieve/status API、Page/Finding list/retrieve API。
- 2026-05-20：ScanJob 建立 API 已強制授權確認、Active 額外授權、明顯第三方重新確認，並記錄 IP、timestamp、user_id、user-agent。
- 2026-05-20：新增 9 項 Django 測試；發現 1 個 create response serializer 錯誤後，新增 2 個回歸測試並修正。
- 2026-05-20：`uv run python backend/manage.py check`、`makemigrations --check --dry-run`、`test apps.scans`、`ruff check backend` 已通過。
- 2026-05-20：新增 Playwright crawler、static scanners、Celery `run_scan_job`、Word report builder、screenshot/report API。
- 2026-05-20：新增 React/Vite/Tailwind/Zustand 前端 MVP，包含註冊/登入、授權 ScanJob form、掃描列表、互動報告、截圖 blob 下載、Word report blob 下載。
- 2026-05-20：新增 `.env.example` 與 `使用說明.md`。
- 2026-05-20：目前後端 13 項測試通過，前端 `npm.cmd run build` 通過。
- 2026-05-20：修正 Playwright browser path，專案預設使用 `.ms-playwright`，避免安裝到使用者層級快取。
- 2026-05-20：使用者明確要求不得再犯全域污染錯誤；已將「Playwright 必須安裝到專案 `.ms-playwright`」寫入 `AGENTS.md`、專案 Skill 與 project rules。
- 2026-05-21：MVP 收尾。爬蟲新增 per-origin RPS 限速（主動 ≤ 2、被動 5）與 401/403/429 blocked 偵測；新增站台層級 GEO FAST 檢查（llms.txt、AI 爬蟲、JS 渲染依賴、語意化區塊、段落可引用性），以 Finding 落地不需 migration。
- 2026-05-21：Django Admin 客製化（後台總覽儀表、Agent token 監控、`AuthorizationConsent` 唯讀）；前端新增 findings 分類/嚴重度篩選並修正截圖高光座標未依縮放換算的對齊 bug。
- 2026-05-21：後端測試由 13 增至 27 項並全數通過；ruff、check、makemigrations --check、前端 build 皆通過。

## Agent Visibility

- 已新增根層 `AGENTS.md`，要求所有進入本專案工作的 agent 先讀 `CLAUDE.md`、`Project_說明.md`、`開發計畫.md`、專案 Skill、references 與本記憶檔。
- 全域入口 `C:\Users\USER\.codex\skills\argus-project\SKILL.md` 只指向專案內正式 Skill，避免專案規則散落到全域。
