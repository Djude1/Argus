# insights 模組規則

Claude 操作 `backend/apps/insights/` 時，本檔在專案層 `CLAUDE.md` 之後自動載入。

## 職責
公開**免費工具**（前台 `/free-tools`），**無 DB model**，邏輯集中在 `analyzers.py`。

## 關鍵端點（`/api/insights/`，`AllowAny`）
| 端點 | View → analyzer | 說明 |
|---|---|---|
| `speed-test/` | `analyze_speed` | 對外部 URL 測速（需 `authorization_confirmed=true`） |
| `phishing-url/` | `score_url_risk` | 釣魚網址啟發式評分（可疑字、短網址等） |
| `phishing-email/` | `analyze_email` | 解析 raw email 的 header / 連結風險 |

## 安全（硬規則，務必保留）
- `analyze_speed` 會**對使用者輸入的外部 URL 發 request** → 已用 `assert_public_url`（`PublicHostError` + `normalize_url` + `socket` / `ipaddress`）**阻擋私有 / 內網位址（SSRF 防護）**。**嚴禁移除**這層檢查。
- ⚠️ **已知殘留風險（待修）**：`analyze_speed` 用 `allow_redirects=True`，**只檢查原始 URL、未對 redirect 後的 `response.url` 重檢** → 公開 URL 若 302 轉址到內網仍會被抓取（SSRF 繞過）。修法：redirect 後對 final host 重做 `assert_public_url`，或改 `allow_redirects=False` 自行逐跳檢查。
- 端點免登入：注意輸入長度上限（`raw_email` ≤ 200k）與必要的限流。

## 禁止事項
| 禁止 | 原因 | 正確做法 |
|---|---|---|
| 移除私有 IP / 內網阻擋（`PublicHostError`） | SSRF，可探測 / 攻擊內網 | 保留並維護 public-host 檢查 |
| 讓外部抓取盲目 follow redirect（**目前現況如此**） | 可繞過 SSRF 檢查打內網 | redirect 後對 final host 重做 `assert_public_url`（目前未做，待修） |
| 在公開端點回傳完整 traceback | 資訊洩漏 | 回標準化錯誤訊息 |
