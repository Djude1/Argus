# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 多層 CLAUDE.md 架構

本專案採用四層結構，各層規則**串接（不覆蓋）**，避免跨層寫矛盾規則：

| 層 | 路徑 | 用途 | git 追蹤 |
|---|---|---|---|
| 使用者層 | `~/.claude/CLAUDE.md` | 個人偏好、OMC 設定 | 不提交 |
| 專案層 | `CLAUDE.md`（本檔） | 團隊共用規範、架構、禁止事項 | ✅ 提交 |
| 子目錄層 | `frontend/CLAUDE.md` 等 | 各模組的具體規則（越深越具體） | ✅ 提交 |
| 個人覆寫層 | `CLAUDE.local.md` | 本機個人微調，不影響他人 | 不提交 |

**子目錄 CLAUDE.md 位置：**
- [`frontend/CLAUDE.md`](frontend/CLAUDE.md) — React/Vite build、App.jsx 操作規範
- [`backend/apps/billing/CLAUDE.md`](backend/apps/billing/CLAUDE.md) — 點數系統唯一入口規則
- [`backend/apps/scans/CLAUDE.md`](backend/apps/scans/CLAUDE.md) — ScanJob 狀態機、Playwright、取消機制

---

## 禁止事項清單（Prohibited Actions）

以下操作**在任何情況下都禁止**，違反可能導致資料損毀、安全漏洞或計費錯誤。

| 禁止事項 | 原因 | 正確做法 |
|---|---|---|
| 直接對 `CoinWallet` 或 `CoinTransaction` 呼叫 `.save()` / `.create()` | 繞過原子交易與冪等保護，導致 race condition | 使用 `billing/services.py` 的函式 |
| 直接執行 `npm run build` | Node v24 + Rollup 4.x 在 Windows 會 `STATUS_STACK_BUFFER_OVERRUN` crash | `cd frontend; .\build-node22.ps1` |
| 在程式碼中硬編碼 API Key / Token / 密碼 | 機密外洩，且一旦推上 git 無法徹底清除 | 放 `.env`，用 `python-dotenv` 讀取 |
| `playwright install` 不加 `PLAYWRIGHT_BROWSERS_PATH` | 污染 `%USERPROFILE%\AppData\Local\ms-playwright` 全域路徑 | `$env:PLAYWRIGHT_BROWSERS_PATH=".ms-playwright"; uv run playwright install chromium` |
| `pip install` 全域安裝 Python 套件 | 污染全域 Python 環境 | `uv add 套件名` |
| 全域 `npm install -g` | 污染全域 Node 環境 | `D:\node22\npm.cmd install 套件名` |
| 修改或刪除已存在的 `CoinTransaction` 紀錄 | 破壞計費稽核軌跡 | 新增 `kind=admin_adjust` 的補正交易 |
| 刪除 `AdminAuditLog` 紀錄 | 破壞合規稽核軌跡 | 禁止刪除，僅可查詢 |
| 在 `scanners.py` / `crawler.py` 直接修改 `ScanJob.status` | 繞過狀態機，導致不一致狀態 | 只在 `tasks.py` 推進狀態 |
| 在 `views.py` 直接 render 使用者個資欄位（email、手機等） | 個資洩漏 | 透過 Serializer 明確 whitelist 欄位 |

---

## 任務完成記錄規則（log 資料夾）

**每次完成任務後，必須在 `log/` 建立記錄並納入同次 git commit。**

- 命名：`log/YYYY-MM-DD_簡短描述.md`，同天多筆加後綴（`fix-a`、`fix-b`）
- 記錄格式（變更內容 / 原因 / 影響範圍 / 驗證方式）詳見 [`docs/log-template.md`](docs/log-template.md)

---

## 文件同步原則

**核心原則：程式碼是唯一事實來源；文件漂移視同 bug，與程式 bug 同等嚴重。**

改了程式 → 同次 commit 同步所有受影響文件；純文件改動 → 先 `Grep` / `Read` 驗證事實再動筆；改完後掃全檔確認無殘留舊事實。

詳細對應規則（規則 A/B/C）與接手文件清單見 [`docs/doc-sync-rules.md`](docs/doc-sync-rules.md)。
MD 修改後必執行核對清單：[`docs/md-checklist.md`](docs/md-checklist.md)。

---

## 常用命令

```powershell
# 啟動（Django 同時 serve 前端 dist，一個命令就能用整個 App）
uv run python backend/manage.py runserver 127.0.0.1:8000

# 前端 build（先 build 才能讓 Django serve）
# ⚠️ 本機 Node v24 在 Windows 上會讓 Rollup STATUS_STACK_BUFFER_OVERRUN，
# 一律用 D:\node22 portable Node，已寫成 helper script：
cd frontend ; .\build-node22.ps1 ; cd ..

# 套用 migration
uv run python backend/manage.py migrate

# 後端測試（約 252 項，以實跑數字為準）
uv run python backend/manage.py test apps

# 單一 app 測試（例如 billing）
uv run python backend/manage.py test apps.billing

# Lint
uv run ruff check backend

# Django 健康檢查
uv run python backend/manage.py check

# Docker（完整部署，含 nginx 反向代理）
docker compose up -d --build
# 改了前端後必須 --build frontend 並強制 reload
docker compose up -d --build frontend
```

---

## 專案架構（非顯而易見的設計）

### 整體資料流
使用者在前端填網址 → `POST /api/scans/`（billing 預扣 coin）→ Celery worker 啟動 Playwright BFS 爬蟲 → 四維 scanner → 可選 Hermes-Agent → 結果寫 DB → 前端 polling 取 findings。

---

### 前端路由地圖（`frontend/src/App.jsx`）

> 所有路由定義在 App.jsx 底部 `<Routes>` 區塊（約第 6460 行起）。

| 路由 | 元件 / 頁面 | 說明 |
|---|---|---|
| `/login` | `LoginPage` | Google OAuth 登入 |
| `/project` | `ProjectPage` | 公開行銷頁：產品特色 |
| `/free-tools` | `FreeToolsPage` | 公開免費分析（測速 / URL 風險 / 郵件風險），呼叫 `/api/insights/*` |
| `/team` | `TeamPage` | 公開行銷頁：團隊介紹 |
| `/purchase` | `PurchasePage` | 購買點數（3 步驟結帳 wizard） |
| `/download` | `DownloadPage` | 下載報告 |
| `/scans` | `ScansPlaceholder` → `ScanListPage` | 掃描列表（需登入） |
| `/scans/:scanId` | `ScanDetailPage` | 掃描結果詳情 + findings |
| `/scans/:scanId/topology` | `TopologyPage` | 網站拓樸圖（ReactFlow） |
| `/reviews` | `ReviewsPage` | 平台評論 |
| `/admin` | → redirect `/admin/overview` | staff 進入點 |
| `/admin/overview` | `AdminOverviewPage` | 後台總覽 |
| `/admin/users` | `AdminUsersPage` | 使用者管理 |
| `/admin/users/:userId` | `AdminUserDetailPage` | 使用者詳情 + 點數調整 |
| `/admin/transactions` | `AdminTransactionsPage` | 交易紀錄 |
| `/admin/reviews` | `AdminReviewsPage` | 評論管理（可回覆） |
| `/admin/scans` | `AdminScansPage` | 掃描任務管理 |
| `/admin/scans/:scanId` | `AdminScanDetailPage` | 掃描詳情（管理員視角） |
| `/admin/content` | `AdminContentPage` | CMS 內容管理 |
| `/admin/plans` | `AdminPlansPage` | 定價方案管理 |
| `/admin/audit-log` | `AdminAuditLogPage` | 操作紀錄（superuser 限定） |

**前端核心檔案：**

| 檔案 | 職責 |
|---|---|
| `frontend/src/App.jsx` | 6500+ 行，所有頁面元件與路由定義全在此 |
| `frontend/src/api.js` | Axios instance，統一處理 base URL 與 CSRF token |
| `frontend/src/store.js` | Zustand 全域狀態（user、wallet 等） |
| `frontend/src/main.jsx` | React entry point，Provider 掛載 |
| `frontend/src/styles.css` | 全域樣式（含 admin 深色 sidebar 變數） |

---

### 後端 API 路由地圖（`backend/config/urls.py`）

| URL 前綴 | Django App | 主要端點 |
|---|---|---|
| `/api/auth/` | `accounts` | `google/`（OAuth）、`register/`、`email-login/`、`me/`（GET/PATCH）、`change-password/` |
| `/api/scans/` | `scans` | `scans/`（CRUD + `status/`/`cancel/`/`report/`/`topology/`/`screenshot`）、`estimate/`、`pages/`、`findings/`、`dashboard/`、`history/`、`audit/`、`findings-by-category/` |
| `/api/billing/` | `billing` | `wallet/`、`plans/`、`purchase/`、`orders/` |
| `/api/reviews/` | `reviews` | `reviews/`（CRUD + thread） |
| `/api/content/` | `content` | `features/`、`team/`、`releases/`、`milestones/`（公開 CMS） |
| `/api/insights/` | `insights` | `speed-test/`、`phishing-url/`、`phishing-email/`（公開免費工具，AllowAny、不扣 coin） |
| `/api/admin/` | `admin_api` | `me/`、`overview/`、`dashboard/`、`users/`、`transactions/`、`scans/`、`reviews/`、`orders/`、`audit-log/`、`announcements/*`、`cms/*` |
| `/django-admin/` | Django Admin | superuser 後門（Django 預設樣式，W4 已移除 jazzmin） |
| `/` ～ `/*` | SPA fallback | 回傳 `frontend/dist/index.html`，由 React Router 處理 |

---

### 關鍵 Model 速查

**ScanJob**（`apps/scans/models.py`）
```
狀態機：queued → crawling → scanning → [agent_testing] → completed
                                                        ↘ failed / cancelled
欄位重點：original_url、status、scan_mode（passive/active）、
         max_depth、max_pages、progress（JSON 即時進度）、
         overall_score、category_scores（JSON）、top_actions（JSON）
```

**CoinWallet**（`apps/billing/models.py`）
```
balance（目前餘額）、total_purchased_ntd、total_scans_used
last_bonus_year / last_bonus_month（月贈點冪等欄位）
→ 所有寫入必須經過 billing/services.py，禁止直接 .save()
```

**CoinTransaction**（`apps/billing/models.py`）
```
wallet FK、amount（正=入帳、負=扣款）、balance_after（異動後餘額快照）
kind（monthly_bonus / purchase / scan_hold / scan_refund / admin_adjust）
scan_job FK（nullable）、plan FK（nullable）、admin_actor FK（nullable）、note
→ 審計不可改；補正交易用 kind=admin_adjust（不是 type，也沒有 manual 值）
```

**AdminAuditLog**（`apps/admin_api/models.py`）
```
admin_actor FK（staff user）、target_user FK（nullable）、
action（coin_adjust / review_reply / review_delete / user_toggle_staff / other）、
target_object_repr、payload（JSON）、created_at
→ 透過 log_admin_action() 集中寫入（調整點數、回覆評論等）
```

**PlatformReview**（`apps/reviews/models.py`）
```
user（一人一則，OneToOne）、rating（1-5）、comment（TextField）、is_featured
→ thread 回覆是獨立 model ReviewMessage（review FK、author、is_admin、body、image）
→ 沒有 content / images(JSON) / parent 欄位（勿沿用舊敘述）
→ 「有幫助」標記：ReviewHelpful / ReviewMessageHelpful（per user 唯一）
```

### Node 22 portable（build 必用）
⚠ 系統 Node v24 + Rollup 4.x 在 Windows 會 crash，build 一律用 `frontend/build-node22.ps1`（D:\node22，v22.22.3 portable）。詳細安裝說明見 [`docs/node22-guide.md`](docs/node22-guide.md)。

### 8 個 Django App 的職責邊界

| app | 職責 | 最重要的檔案 |
|---|---|---|
| `accounts` | User model（繼承 AbstractUser）、Google OAuth、Email 註冊/登入、改密碼 | `views.py` |
| `scans` | **核心**：ScanJob 狀態機、Playwright 爬蟲、四維 scanner、Word 報告、合作式 cancel | `tasks.py` `crawler.py` `scanners.py` |
| `agent` | Phase 2 Hermes-Agent：provider chain + tool calling loop（預設 `ARGUS_AGENT_ENABLED=false`） | `providers.py` `loop.py` `runner.py` |
| `billing` | 點數錢包；**`services.py` 是 wallet 唯一寫入入口**，禁止繞過直接改 model | `services.py` `signals.py` |
| `reviews` | 平台評論（一人一則 + thread + 圖片） | `models.py` `views.py` |
| `admin_api` | React `/admin/*` 用的 REST API + AdminAuditLog | `views.py` `permissions.py` |
| `content` | CMS（ProjectFeature / TeamMember / AppRelease），公開 API | `models.py` `admin.py` |
| `insights` | 公開免費分析工具（測速 / 釣魚 URL / 釣魚郵件），AllowAny、不扣 coin；供公開頁 `/free-tools` 使用 | `views.py` `analyzers.py` |

### 前端：巨型單檔架構
`frontend/src/App.jsx` 是 **6500+ 行的單檔**，包含所有頁面與元件。修改前必須先 grep 定位，不要從頭瀏覽。路由都在 App.jsx 底部 `<Routes>` 區塊。

### Billing 的冪等安全閘
`billing/services.py` 所有函式都用 `select_for_update` + `transaction.atomic` + 冪等判斷（e.g. `last_bonus_year/month`）。掃描取消或失敗時 worker 和 cancel API 都會呼叫 `refund_full_for_scan`，兩邊都呼叫是安全的。

### Django 直接 serve 前端
開發時不需要另開 Vite dev server，Django `runserver` 透過 `config/urls.py` 的 SPA fallback 直接服務 `frontend/dist`。**必須先 build 前端**，改了 React code 要重 build 才會生效。

### Playwright 瀏覽器路徑
Chromium 必須裝在專案 `.ms-playwright`，不可污染全域：
```powershell
$env:PLAYWRIGHT_BROWSERS_PATH=".ms-playwright"; uv run playwright install chromium
```

### 三種管理介面
- **前台**：`http://127.0.0.1:8000/` — 一般使用者
- **React 後台**：`/admin/*` — staff 進入（`IsAdminUser`），superuser 多看「操作紀錄」
- **Django Admin**：`/django-admin/` — superuser 後門，Django 預設樣式（W4 已移除 jazzmin）

### 掃描 Coin 扣點流程
建立掃描 → `hold_for_scan(max_pages × 10)` → worker 完成 → `settle_scan_actual(actual_pages × 10)` 退差 → 失敗/取消 → `refund_full_for_scan` 全退。

---

## 必須遵守的規則

- 所有回覆一律使用**繁體中文**，程式碼註釋也是
- 絕對不能洩漏任何與使用者相關的個資或訊息

## 環境隔離

- Python 套件管理統一使用 `uv`（`uv add` / `uv run`）
- 任何套件安裝必須在 `.venv` 虛擬環境或 Docker 容器內執行，禁止污染全域環境

## 敏感資訊

- API Key、密碼、Token、模型路徑一律放 `.env`
- 禁止在程式碼中硬編碼任何敏感資訊
- 使用 `python-dotenv` 讀取

---

## 行為準則（每次對話必須遵守，優先順序最高）

> 以下準則旨在減少 LLM 常見的程式錯誤。偏向謹慎而非速度。對於極簡單的任務可自行判斷，但原則上必須遵守。

### 1. 動手前先思考

**不要假設。不要隱藏困惑。主動說明取捨。**

實作前必須：
- 明確說出你的假設。若不確定，先問。
- 若有多種解釋方式，全部列出，不可自行靜默選擇。
- 若有更簡單的方法，說出來。必要時提出異議。
- 若有不清楚的地方，停下來，說明哪裡不清楚，再問使用者。

### 2. 簡潔優先

**用最少的程式碼解決問題，不寫任何推測性內容。**

- 不加任何未被要求的功能。
- 不為只使用一次的程式碼建立抽象層。
- 不加任何未被要求的「彈性」或「可設定性」。
- 不為不可能發生的情境加錯誤處理。
- 若你寫了 200 行但 50 行就能解決，請重寫。

自我檢查：「資深工程師會說這過度複雜嗎？」若是，請簡化。

### 3. 精準修改

**只動必須動的地方，只清理自己造成的問題。**

修改現有程式碼時：
- 不「順便改進」相鄰的程式碼、註解或格式。
- 不重構沒有壞掉的東西。
- 配合現有風格，即使你有不同偏好。
- 若發現無關的殭屍程式碼，提出來，但不要自行刪除。

你的改動造成孤兒時：
- 移除因**你的改動**而變成未使用的 import / 變數 / 函式。
- 不移除改動前就已存在的殭屍程式碼，除非被要求。

驗證標準：每一行被改動的程式碼，都必須能直接追溯到使用者的需求。

### 4. 深度理解優先、持續更新交接

**每次思考前，先對目前專案有深度了解，並清楚使用者的真實需求。**

思考前必須：
- 讀取專案的現況文件（如 CLAUDE.md、現況快照、交接資料）確認目前狀態
- 確認使用者的需求背後的**真正目的**（Why），不只是表面請求（What）
- 若不確定專案現況，先查再動手，不猜測

完成任何任務後必須：
- 更新記憶索引與對應 memory 檔案（新發現、決策理由、地雷）
- 更新相關 `.md` 文件記錄本次決策
- 若新增或修改了 Skill，同步更新 `CLAUDE.md` 的 Skills 表格

**目標：下次接觸此專案時，不需要使用者重新解釋，即可立刻掌握現況並繼續工作。**

**對話開始時必做（每個專案依自身規則執行）：**
- 檢查不在 Git 上的機密設定檔有無變更（如 `.env`、金鑰 JSON）
- 執行 git pull 取得最新遠端狀態，處理任何累積的待辦 log

### 5. 目標導向執行

**定義成功條件，循環直到驗證通過。**

將任務轉化為可驗證的目標：
- 「新增驗證」→「先為不合法輸入寫測試，再讓測試通過」
- 「修復 bug」→「先寫能重現 bug 的測試，再讓測試通過」
- 「重構 X」→「確認重構前後測試皆通過」

多步驟任務必須先說明計畫：
```
1. [步驟] → 驗證：[確認方式]
2. [步驟] → 驗證：[確認方式]
3. [步驟] → 驗證：[確認方式]
```

強成功條件讓你能獨立循環執行；弱成功條件（如「讓它能動」）需要不斷釐清，問題往往在出錯後才被發現。

### 6. 每次更新後必須徹底檢查，直到無錯誤才算完成

**任何修改、新增、刪除動作完成後，必須自行執行完整檢查與測試，確認無任何錯誤，才能進入下一個環節。**

- 不能只說「應該沒問題」或「邏輯上正確」就結束
- 若測試發現錯誤，**立即修正**，再重新測試，循環直到全部通過
- 每個環節驗證通過後才能繼續下一步，不可跳過
- 無法自動測試的項目（如實機、硬體），必須明確告知使用者「需要你手動驗證以下項目」，並列出清單

**驗證方式依情境選擇：**
| 情境 | 驗證方式 |
|------|----------|
| Python 修改 | `uv run python -c "import 模組"` 或跑相關測試 |
| API 端點修改 | 直打 API 確認回應正確 |
| Flutter 修改 | `flutter analyze`（靜態檢查）+ 提醒實機測試 |
| git 操作 | 確認 status / log 符合預期後才執行 |
| 設定檔修改 | 重新載入並確認生效 |
| cloudflared `config.yml` 修改 | 見 [`docs/cloudflared-guide.md`](docs/cloudflared-guide.md)，絕對不要只改 user 版 |
| 規則/MD 檔案修改 | 執行 [`docs/md-checklist.md`](docs/md-checklist.md)，每項逐一確認 |

---

## 特定操作指南（遇到時再查）

| 場景 | 文件 |
|---|---|
| cloudflared ingress 設定、跨 zone DNS | [`docs/cloudflared-guide.md`](docs/cloudflared-guide.md) |
| RTK 使用規則（token 壓縮） | [`docs/rtk-guide.md`](docs/rtk-guide.md) |
| MD / 文件修改核對清單 | [`docs/md-checklist.md`](docs/md-checklist.md) |
| 文件同步詳細規則 A/B/C | [`docs/doc-sync-rules.md`](docs/doc-sync-rules.md) |
| log 記錄格式範本 | [`docs/log-template.md`](docs/log-template.md) |
| Node 22 portable 詳細安裝說明 | [`docs/node22-guide.md`](docs/node22-guide.md) |
