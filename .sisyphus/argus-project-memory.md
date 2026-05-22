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
- 2026-05-21（第二輪）：續做 MVP 周邊收尾——新增 `UserScanQuota`（每月配額預設 20）、`Page.headers`/`element_boxes` 欄位（migration 0002）、`rerun_scan` management command（cache replay）、react-router-dom v7 三路由（/login、/scans、/scans/:scanId）、完整 Docker Compose 配置（web/worker/redis/db/nginx）。後端測試增至 32 項全綠；React Router 與 Docker 設定需使用者手動驗證。
- 2026-05-21（第二輪）：使用者再次強調「禁止全域安裝」；確認本輪所有依賴皆專案層級（npm install 在 frontend/、uv 在 Docker image 內、Playwright 路徑 `.ms-playwright` 或 image 內 `/ms-playwright`）。
- 2026-05-21（第三輪）：使用者要求建立 superuser `1124`/`1124`、一般使用者改 Google OAuth。`1124` 透過 Django shell 繞過密碼驗證器建立（僅限本機 dev DB）；一般使用者登入改用 `/api/auth/google/`（`google-auth` 驗證 ID Token，首次以 email 為 username 自動建立帳號）。`RegisterView` / `/api/auth/token/` / `/api/auth/token/refresh/` 與 `accounts/serializers.py` 一併移除（孤兒）。`GOOGLE_OAUTH_CLIENT_ID` 由 Vite envDir + envPrefix 設定讓 backend 與 frontend 共用同一個變數。`@react-oauth/google` 安裝於 `frontend/node_modules`；`google-auth`、`requests` 透過 `uv add` 進 `.venv`，皆未污染全域。後端測試由 32 增至 36 項全綠。
- 2026-05-21（第四輪）：使用者明確只會跑 3 命令（`docker compose build`/`up`、`runserver`），其餘自動化。改用 data migration `accounts/0002_bootstrap_superuser` 從 `.env` 讀 username/password 自動建 `1124`/`1124`（idempotent，SQLite 與 Postgres 都生效）。Django 直接服務前端 SPA（`config/urls.py` 加 `/assets/` 與 SPA fallback、`TEMPLATES.DIRS` 加 `frontend/dist`），runserver 一個命令就能用整個 React UI。`frontend/src/api.js` `baseURL` 改相對 `/api`。nginx.conf 加 `/static/` 反代到 web。`.env` 內 `DJANGO_SECRET_KEY` 與 `JWT_SECRET_KEY` 強化為 64-byte random。Google Client ID 已從使用者提供的 `client_secret_*.json` 檔名萃取寫入 `.env`（沒讀 JSON 內容，避免 Secret 進 context）。
- 2026-05-21（第五輪，暫時性）：Google OAuth 撞到 `origin_mismatch`，使用者要求加跳過登入後門。新增 `DevLoginView`（`/api/auth/dev-login/`）以 `settings.DEBUG=True` 為前提；DEBUG=False 自動 404。前端 LoginForm 加「🛠️ 跳過 Google 登入」按鈕。5 處 code 區塊都標 `DEV LOGIN BACKDOOR — REMOVE WHEN GOOGLE OAUTH IS FULLY WORKING` 註解，Google origin 生效後請 grep 此字串刪除整塊。測試由 36 增至 40 項全綠。
- 2026-05-21（第六輪）：F5 / 直接輸入網址（deep link）抗性 + Docker Compose 端到端驗證。修補三處破口：(1) axios 401 response interceptor — 過期 token 自動清除並導回 `/login?next=<原路徑>`；(2) `RequireAuth` / `LoginPage` / `LoginForm` 串接 `?next=` 參數，讓使用者未登入直接打 deep link 或 token 過期後 F5 都能登入後回到原頁；(3) `frontend/Dockerfile` 缺 `GOOGLE_OAUTH_CLIENT_ID`（build context 是 `./frontend`，根目錄 .env 進不來）— 改用 docker-compose build args 注入並寫入 `/.env` 給 Vite envDir 讀。Docker compose 5 個 container 全部 up；HTTP smoke 對 `/`、`/scans`、`/scans/123`、`/login?next=...`、`/assets/*`、`/api/scans/`（401）、帶 token 後 `/api/scans/`（200）、`/admin/`（302→200）、`/api/auth/dev-login/`（200）全部通過。aiglasses.qzz.io（Cloudflare + Vite dev server，另一個專案）被確認為 Argus 的掃描目標而非部署位置；其 robots.txt 未阻擋 Argus UA。
- 2026-05-21（第七輪）：實際對 aiglasses.qzz.io 觸發掃描時失敗，UI 顯示「✗ 掃描失敗：Error」。Root cause：`pyproject.toml` 指定 `playwright>=1.48,<2` 但 uv lock 解析到 1.60.0，`Dockerfile` base image 仍是 `mcr.microsoft.com/playwright/python:v1.48.0-jammy`，預裝的 chromium 版本對不上 1.60.0 需要的 `chromium_headless_shell-1223`。修：base image 升到 `v1.60.0-jammy`。同時改善 `tasks.py` 的 except 處理，`error_message` 從 `exc.__class__.__name__`（只存 "Error"）改為 `f"{class}: {str(exc)[:500]}"`，未來失敗在 UI 可診斷。重 build web/worker image 後重新掃描 aiglasses.qzz.io：completed，pages=11、findings=112、overall_score=20（top actions 全是「頁面未使用 HTTPS」，因該站僅 http）。**地雷**：每次 `docker compose up -d` recreate web 後，frontend nginx 會把 `web:8000` 卡在舊 IP → 502 Bad Gateway，需 `docker compose restart frontend` 強制重新解析（未來考慮 nginx resolver + variable-based proxy_pass 修掉根因）。
- 2026-05-21（第八輪）：UI 兩個明確 bug + 報告 UX 改善。(2) Findings 列表 112 筆扁平展開很雜亂（11 頁 × ~10 種 finding 類型），改成「分類+標題」分組顯示：每組顯示嚴重度色塊、CATEGORY pill、總計頁面數，點開展開該群組底下每一頁與 evidence；同類嚴重度取群內最高，群組排序按 SEVERITY_RANK→category→count；自動展開包含當前 selectedFinding 的群組。新增 `FindingsGroupList` 元件、`buildFindingGroups` 純函式（依 `category::title` 鍵分組）、`SEVERITY_RANK` 常數。styles.css 加 `.finding-group*`、`.finding-item*`、`.category-pill.cat-{security,seo,aeo,geo,ux}`、`.screenshot-caption`。(3) ScreenshotCanvas 原永遠載 `pages[0]` 截圖，改根據 `selectedFinding.page` 找對應 Page；無選 / 站台層級 finding（page=null）fallback `pages[0]`；高光框只繪當前 page 的 findings 避免跨頁畫框；新增頁面標題 caption。
- 2026-05-22（第十二輪）：CSS 全域化。styles.css 加 `:root` 設計 token（深藍 navy 6 階、cyan 強調 4 色、deep 介面文字 2 色、tone good/medium/bad 7 色、圓角 3、陰影 2），把原本散在各 class 寫死的 hex 純色全部換成 `var()`，要換主題色改 `:root` 一處即可（驗證：6 個深藍 hex 在 CSS 內僅出現各 1 次＝只在 `:root` 定義，無殘留無循環）。半透明 glow/border 的 rgba 保留原值（視覺隨主色走）。重複的 utility 組合抽成全域語意 class：`.hint-text`（text-sm text-slate-500，9 處）、`.hint-text-sm`（text-xs text-slate-400，7 處）；只用一次的組合不抽（避免過度抽象）。grep 確認專案執行程式碼本來就零硬編碼絕對路徑（settings.py 用 Path 動態推導、相對路徑、docker 容器內路徑），可攜性無虞；文件/規則檔裡的 `D:\RTK`、`D:\GitHub_Project\Argus` 是環境描述，不影響運作。

- 2026-05-22（第十一輪）：截圖區放大 + 紅框反饋修正。使用者反映詳情頁中央截圖太小（左 sidebar 360 + 右 findings 360 夾擊，截圖實寬僅 ~500px）。`ScanLayout` 改雙模式：list-mode（`/scans`）sidebar inline 360px grid；detail-mode（`/scans/:id`）sidebar 抽離為 fixed drawer overlay（translateX 動畫 + backdrop），主內容拿全寬，截圖可到 ~840px。詳情頁頂部加工具列：`drawer-toggle`（☰ 展開列表/建立掃描）+ `back-to-list-button`。另一回饋：點 finding 沒紅框 — root cause 是該掃描目標多數 finding `bounding_box=null`（站台層級問題如 HTTPS/CSP，加上 aiglasses 是 SPA、scanner 看 server HTML 沒 h1/form/main）。修正：`ScreenshotCanvas` 加 `whole-page-highlight` — selectedFinding 沒 bounding_box（或選到別頁 finding）時，截圖畫整頁紅色 pulse 外框，保證「點了一定有視覺反饋」；元素級 finding 仍畫精確 highlight-box。站台 banner 文字精簡（移除「無對應頁面元素座標」技術說明）。（使用者覺得第九輪後仍單調，要求 dashboard / sidebar / 詳情頁 / 設定頁強化）。新增 4 個純 SVG/CSS 視覺化元件 — `CountUp`（requestAnimationFrame ease-out cubic，整數/小數自適應）、`StackedBar`（水平堆疊比例 + 圖例）、`SeverityBarChart`（5 嚴重度橫條 + 自適應 max scale + glow shadow）、`LineChart`（XY 軸 + 格線 + 點標註 + 數值 + drop-shadow）；以及完整 keyframes（`fade-up`、`bar-grow`、`ring-draw`、`pulse-soft`、`shimmer`、`fade-in`）。Dashboard：StatTile 數字用 CountUp 動畫；加 2 個新 panel（「Findings 嚴重度分佈」用 SeverityBarChart、「各類別 finding 佔比」用 StackedBar，後者需 Promise.all 串接 `/findings-by-category/`）。History：sparkline 升級為 LineChart（含日期 X 軸與分數 Y 軸標註）。掃描列表（sidebar）：scan-card 加左側色帶（依分數 tone good/medium/bad 配漸層 + glow）、加「與該 origin 上一次分數比較」delta 箭頭。掃描詳情：頂部新增 `report-viz` 區（左嚴重度長條、右類別堆疊條）；Top Actions 從純文字段落改為可點按鈕（點了會 selectFinding 自動定位到對應 finding）；改為 gradient 卡片背景。Settings：新 `quota-panel` 含大型配額進度條（漸層 + glow + tone 自適應 good/medium/bad）；新增「累計掃描」「累計 Findings」「技術棧」三張 stat-card；CountUp 在多處。全域動畫：所有 `.stat-tile / .panel / .dashboard-hero` 進場 fade-up 0.4s；`.stat-tile / .scan-card / .history-card` hover translate-y -2px + shadow；bar 動畫 `bar-grow` 0.7s cubic-bezier。前端 bundle 從 262.02 → 270.05 KB（+8 KB），CSS 從 40.51 → 53.15 KB（+13 KB），無額外套件。所有 8 個 SPA 路由仍 200，新 viz class 都正確進 production bundle。**後端新增 4 個 aggregate endpoint**（不需新 model，從 ScanJob/Finding/AuthorizationConsent/UserScanQuota 聚合）：`/api/dashboard/`（總覽 + 各類別平均 + 嚴重度統計 + 最近 5 次 + 本月配額）、`/api/history/`（每 origin 歷次分數 + delta）、`/api/audit/`（scan_created/completed/failed/authorization 事件時間軸）、`/api/findings-by-category/`（跨掃描 finding 按 category::title Counter 聚合）。**前端**：新增 `TopNav`（深色高科技 nav，深藍漸層 + 霓虹 cyan 強調）、6 個 NavLink（Dashboard / 掃描 / 歷史 / 活動 / 分類 / 設定）；新增 5 個分頁 `DashboardPage`（Hero + 4 StatTile + 5 個 category ScoreRing + 最近 5 次列表）、`HistoryPage`（Sparkline SVG + delta tone + 歷次列表）、`AuditPage`（左 timeline marker 風格事件流）、`CategoriesPage`（5 category tab + 重複 finding 列表）、`SettingsPage`（4 settings card + about 區塊）；輔助元件 `ScoreRing`（SVG circle + stroke-dashoffset 動畫 + 三色 tone）、`StatTile`、`Sparkline`。**報告區（FindingsWorkspace）**：頂部加 page tabs（全站/首頁/各頁，顯示該頁 finding 數），URL 用 `?page=<id>` 串接 F5 還原；ScreenshotCanvas 改受控（接收 targetPage prop），不再從 selectedFinding 推算；selectFinding 時自動切到對應 page tab，站台層級 finding 切回「全站」；**(1) 站台級 finding 紅色 banner**：當 selectedFinding 沒 bounding_box 時截圖頂部覆蓋紅色漸層 banner（含 severity / CATEGORY pill / 警示文字 / 備註）。CSS 從 21 → 40 kB（+19 KB，含完整深色 reskin），JS 從 247 → 261 kB（+14 KB）。Routes：`/dashboard /scans /scans/:id /history /audit /categories /settings /login?next=`，預設 `*` redirect 到 `/dashboard`。所有 SPA routes + 4 個新 API endpoint 端到端 smoke 全部 200，後端 40 tests + ruff 通過。**未做（使用者下一輪再評估）**：finding bounding_box 對 H1/img/form/main 以外的元素（CSP、HSTS 等只能站台層級畫 banner）；audit log 改為真正的 model + middleware（目前是從現有資料派生）；同網址歷史的時間軸圖（目前只有 sparkline 與列表）。

## Agent Visibility

- 已新增根層 `AGENTS.md`，要求所有進入本專案工作的 agent 先讀 `CLAUDE.md`、`Project_說明.md`、`開發計畫.md`、專案 Skill、references 與本記憶檔。
- 全域入口 `C:\Users\USER\.codex\skills\argus-project\SKILL.md` 只指向專案內正式 Skill，避免專案規則散落到全域。
