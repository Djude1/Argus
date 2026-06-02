# reviews 模組規則

Claude 操作 `backend/apps/reviews/` 時，本檔在專案層 `CLAUDE.md` 之後自動載入。

## 職責
平台評論：**一人一則** + thread 補充 + 圖片附件 + 「有幫助」點讚。

## Models
| Model | 重點 |
|---|---|
| `PlatformReview` | `OneToOne` user（**一人一則**）、`rating` 1-5（**建立時設定一次**）、`is_featured`（admin 精選） |
| `ReviewMessage` | 評論串訊息（`is_admin` 區分樣式；`image` 存 `MEDIA_ROOT/review_images/`） |
| `ReviewHelpful` / `ReviewMessageHelpful` | 一人一次點讚（`UniqueConstraint`） |

## 關鍵端點（`/api/reviews/`）
- `""`（list）、`mine/`、`<id>/messages/`（發訊息）、`<id>/helpful/`、`messages/<id>/helpful/`
- **admin 回覆走 `admin_api`**：`reviews/<id>/reply`（產生 `is_admin=True` 訊息 + 寫 audit）

## 禁止事項
| 禁止 | 原因 | 正確做法 |
|---|---|---|
| 讓使用者建立多則 `PlatformReview` | 違反一人一則 | 維持 `OneToOne`；補充走 `ReviewMessage` |
| 建立後修改 `rating` | 評分公信力 | `rating` 僅建立時可設 |
| 不驗證 `image` 上傳型別 / 大小 | 儲存濫用 / 安全 | serializer 驗證型別與大小 |
