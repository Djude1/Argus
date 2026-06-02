# admin_api 模組規則

Claude 操作 `backend/apps/admin_api/` 時，本檔在專案層 `CLAUDE.md` 之後自動載入。

## 職責
React `/admin/*` 後台用的 REST API + `AdminAuditLog` 稽核。端點**刻意扁平、隱藏內部 model**（AgentSession / Page / Finding 等不外露）。

## 權限
- 一般後台端點：`IsAdminUser`（`is_staff=True`，與 Django Admin 一致）。
- 高敏感（audit-log 等）：`IsSuperuser`（`permissions.py`）。

## 關鍵檔案 / 端點（`/api/admin/`）
- `views.py`：`overview`、`users`、`users/<id>`、`users/<id>/adjust-coin`、`transactions`、`reviews`、`reviews/<id>/reply`、`scans`、`scans/<id>`、`orders`、`dashboard`、`audit-log`、`announcements/*`
- `cms_views.py`：`cms/(features|team|releases|plans)` 寫入端點（ModelViewSet）
- `models.py`：`AdminAuditLog`（action：`coin_adjust` / `review_reply` / `review_delete` / `user_toggle_staff` / `other`；`log_admin_action()` 集中寫入、**失敗不擋業務**）、`Announcement`（常駐/臨時公告）
- `serializers.py`：輸出欄位 **whitelist**

## 重點
- 調點數一律走 `billing.services.admin_adjust`，**禁止**直接改 `CoinWallet`。
- 每筆後台敏感操作都呼叫 `log_admin_action` 留痕。

## 禁止事項
| 禁止 | 原因 | 正確做法 |
|---|---|---|
| 刪除 / 修改 `AdminAuditLog` | 破壞合規稽核軌跡 | 僅可查詢 |
| 直接 `CoinWallet` / `CoinTransaction` `.save()` | 繞過冪等與原子交易 | `billing.services.admin_adjust` |
| 在 `views` 直接 render 個資欄位 | 個資外洩 | 透過 serializer whitelist |
| 敏感操作不寫 audit | 合規破口 | 呼叫 `log_admin_action` |
