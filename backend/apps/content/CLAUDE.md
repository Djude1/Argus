# content 模組規則

Claude 操作 `backend/apps/content/` 時，本檔在專案層 `CLAUDE.md` 之後自動載入。

## 職責
**公開 CMS 讀取 API**。Models：`ProjectFeature`、`TeamMember`、`ProjectMilestone`、`AppRelease`。

## 關鍵端點（`/api/content/`，公開唯讀 GET）
| 端點 | View | 對應前台 |
|---|---|---|
| `features/` | `features_list` | `/project` 特色卡片 |
| `team/` | `team_list` | `/team` 成員 |
| `releases/` | `releases_list` | `/download` 版本 |
| `milestones/` | `milestones_list` | `/project` timeline |

## 重點
- 本 app **只服務公開讀取**；**寫入 / 編輯走 `admin_api` 的 `cms_views`**（`/api/admin/cms/*`，需 `IsAdminUser`）。
- `TeamMember` 有 `email` / `github_url` 等欄位，公開端點要小心只輸出可公開欄位。

## 禁止事項
| 禁止 | 原因 | 正確做法 |
|---|---|---|
| 在 content 加任何寫入 / 編輯端點 | 公開可寫＝內容被竄改 | 寫入一律走 `admin_api/cms`（`IsAdminUser`） |
| 公開端點回傳 `TeamMember.email` 等個資 | 個資外洩 | serializer 只輸出公開欄位 |
